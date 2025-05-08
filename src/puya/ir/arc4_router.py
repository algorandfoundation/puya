import typing
from collections.abc import Iterable, Mapping, Sequence

import attrs

from puya import (
    artifact_metadata as md,
    log,
)
from puya.avm import OnCompletionAction
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError
from puya.ir.arc4_types import is_equivalent_effective_array_encoding, wtype_to_arc4_wtype
from puya.parse import SourceLocation
from puya.utils import set_add

__all__ = [
    "create_abi_router",
    "AWSTContractMethodSignature",
]

logger = log.get_logger(__name__)

ALL_VALID_APPROVAL_ON_COMPLETION_ACTIONS = {
    OnCompletionAction.NoOp,
    OnCompletionAction.OptIn,
    OnCompletionAction.CloseOut,
    OnCompletionAction.UpdateApplication,
    OnCompletionAction.DeleteApplication,
}


@attrs.frozen(kw_only=True)
class AWSTContractMethodSignature:
    target: awst_nodes.ContractMethodTarget
    parameter_types: Sequence[wtypes.WType]
    return_type: wtypes.WType


def _btoi(
    bytes_arg: awst_nodes.Expression, location: SourceLocation | None = None
) -> awst_nodes.IntrinsicCall:
    return awst_nodes.IntrinsicCall(
        op_code="btoi",
        stack_args=[bytes_arg],
        wtype=wtypes.uint64_wtype,
        source_location=location or bytes_arg.source_location,
    )


def _txn(
    immediate: str, wtype: wtypes.WType, location: SourceLocation
) -> awst_nodes.IntrinsicCall:
    return awst_nodes.IntrinsicCall(
        op_code="txn",
        immediates=[immediate],
        wtype=wtype,
        source_location=location,
    )


def _txn_app_args(index: int, loc: SourceLocation) -> awst_nodes.IntrinsicCall:
    return awst_nodes.IntrinsicCall(
        op_code="txna",
        immediates=["ApplicationArgs", index],
        source_location=loc,
        wtype=wtypes.bytes_wtype,
    )


def create_block(
    location: SourceLocation, comment: str | None, *stmts: awst_nodes.Statement
) -> awst_nodes.Block:
    return awst_nodes.Block(source_location=location, body=stmts, comment=comment)


def call(
    location: SourceLocation, sig: AWSTContractMethodSignature, *args: awst_nodes.Expression
) -> awst_nodes.SubroutineCallExpression:
    return awst_nodes.SubroutineCallExpression(
        target=sig.target,
        args=[awst_nodes.CallArg(name=None, value=arg) for arg in args],
        wtype=sig.return_type,
        source_location=location,
    )


def app_arg(
    index: int,
    wtype: wtypes.WType,
    location: SourceLocation,
) -> awst_nodes.Expression:
    value = _txn_app_args(index, location)
    if wtype == wtypes.bytes_wtype:
        return value
    return awst_nodes.ReinterpretCast(
        source_location=location,
        expr=value,
        wtype=wtype,
    )


def _non_zero(value: awst_nodes.Expression) -> awst_nodes.Expression:
    location = value.source_location
    return awst_nodes.NumericComparisonExpression(
        lhs=value,
        rhs=constant(0, location),
        operator=awst_nodes.NumericComparison.ne,
        source_location=location,
    )


def _is_zero(value: awst_nodes.Expression) -> awst_nodes.Expression:
    location = value.source_location
    return awst_nodes.NumericComparisonExpression(
        lhs=value,
        rhs=constant(0, location),
        operator=awst_nodes.NumericComparison.eq,
        source_location=location,
    )


def return_(value: bool, location: SourceLocation) -> awst_nodes.ReturnStatement:  # noqa: FBT001
    return awst_nodes.ReturnStatement(
        value=awst_nodes.BoolConstant(value=value, source_location=location),
        source_location=location,
    )


def reject(location: SourceLocation) -> awst_nodes.ReturnStatement:
    return return_(False, location)  # noqa: FBT003


def approve(location: SourceLocation) -> awst_nodes.ReturnStatement:
    return return_(True, location)  # noqa: FBT003


def on_completion(location: SourceLocation) -> awst_nodes.Expression:
    return _txn("OnCompletion", wtypes.uint64_wtype, location)


def route_bare_methods(
    location: SourceLocation,
    bare_methods: Mapping[md.ARC4BareMethod, AWSTContractMethodSignature],
) -> awst_nodes.Block | None:
    bare_blocks = dict[OnCompletionAction, awst_nodes.Block]()
    for method, sig in bare_methods.items():
        bare_location = method.config_location
        bare_block = create_block(
            bare_location,
            sig.target.member_name,
            *assert_create_state(method),
            awst_nodes.ExpressionStatement(expr=call(bare_location, sig)),
            approve(bare_location),
        )
        for oca in method.allowed_completion_types:
            if bare_blocks.setdefault(oca, bare_block) is not bare_block:
                logger.error(
                    f"cannot have multiple bare methods handling the same "
                    f"OnCompletionAction: {oca.name}",
                    location=bare_location,
                )
    return create_block(
        location,
        "bare_routing",
        *_maybe_switch(
            on_completion(location),
            {constant(oca.value, location): block for oca, block in bare_blocks.items()},
        ),
    )


def log_arc4_result(
    location: SourceLocation, result_expression: awst_nodes.Expression
) -> awst_nodes.ExpressionStatement:
    abi_log_prefix = awst_nodes.BytesConstant(
        source_location=location,
        value=0x151F7C75.to_bytes(4),
        encoding=awst_nodes.BytesEncoding.base16,
    )
    abi_log = awst_nodes.BytesBinaryOperation(
        source_location=location,
        left=abi_log_prefix,
        op=awst_nodes.BytesBinaryOperator.add,
        right=awst_nodes.ReinterpretCast(
            expr=result_expression,
            wtype=wtypes.bytes_wtype,
            source_location=result_expression.source_location,
        ),
    )
    log_op = awst_nodes.IntrinsicCall(
        op_code="log",
        stack_args=[abi_log],
        wtype=wtypes.void_wtype,
        source_location=location,
    )
    return awst_nodes.ExpressionStatement(log_op)


def assert_create_state(method: md.ARC4Method) -> Sequence[awst_nodes.Statement]:
    app_id = _txn("ApplicationID", wtypes.uint64_wtype, method.config_location)
    match method.create:
        case awst_nodes.ARC4CreateOption.allow:
            # if create is allowed but not required, we don't need to check anything
            return ()
        case awst_nodes.ARC4CreateOption.disallow:
            condition = _non_zero(app_id)
            error_message = "can only call when not creating"
        case awst_nodes.ARC4CreateOption.require:
            condition = _is_zero(app_id)
            error_message = "can only call when creating"
        case invalid:
            typing.assert_never(invalid)
    return [
        awst_nodes.ExpressionStatement(
            awst_nodes.AssertExpression(
                condition=condition,
                error_message=error_message,
                source_location=method.config_location,
            )
        )
    ]


def constant(value: int, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.UInt64Constant(value=value, source_location=location)


def left_shift(value: awst_nodes.Expression, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.UInt64BinaryOperation(
        source_location=location,
        left=constant(1, location),
        op=awst_nodes.UInt64BinaryOperator.lshift,
        right=value,
    )


def bit_and(
    lhs: awst_nodes.Expression, rhs: awst_nodes.Expression, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.UInt64BinaryOperation(
        source_location=location,
        left=lhs,
        op=awst_nodes.UInt64BinaryOperator.bit_and,
        right=rhs,
    )


def uint64_sub(
    lhs: awst_nodes.Expression, rhs: awst_nodes.Expression, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.UInt64BinaryOperation(
        source_location=location,
        left=lhs,
        op=awst_nodes.UInt64BinaryOperator.sub,
        right=rhs,
    )


def bit_packed_oca(
    allowed_oca: Iterable[OnCompletionAction], location: SourceLocation
) -> awst_nodes.Expression:
    """Returns an integer constant, where each bit corresponding to an OnCompletionAction is
    set to 1 if that action is allowed. This allows comparing a transaction's on completion value
    against a set of allowed actions using a bitwise and op"""
    bit_packed_value = 0
    for value in allowed_oca:
        bit_packed_value |= 1 << value.value
    return constant(bit_packed_value, location)


def check_allowed_oca(
    allowed_ocas: Sequence[OnCompletionAction], location: SourceLocation
) -> Sequence[awst_nodes.Statement]:
    not_allowed_ocas = sorted(
        a for a in ALL_VALID_APPROVAL_ON_COMPLETION_ACTIONS if a not in allowed_ocas
    )
    if not not_allowed_ocas:
        # all actions are allowed, don't need to check
        return ()
    match allowed_ocas, not_allowed_ocas:
        case [[single_allowed], _]:
            condition: awst_nodes.Expression = awst_nodes.NumericComparisonExpression(
                lhs=on_completion(location),
                rhs=awst_nodes.UInt64Constant(
                    source_location=location,
                    value=single_allowed.value,
                    teal_alias=single_allowed.name,
                ),
                operator=awst_nodes.NumericComparison.eq,
                source_location=location,
            )
        case _, [single_disallowed]:
            condition = awst_nodes.NumericComparisonExpression(
                lhs=on_completion(location),
                rhs=awst_nodes.UInt64Constant(
                    source_location=location,
                    value=single_disallowed.value,
                    teal_alias=single_disallowed.name,
                ),
                operator=awst_nodes.NumericComparison.ne,
                source_location=location,
            )
        case _:
            condition = bit_and(
                left_shift(on_completion(location), location),
                bit_packed_oca(allowed_ocas, location),
                location,
            )
    oca_desc = ", ".join(a.name for a in allowed_ocas)
    if len(allowed_ocas) > 1:
        oca_desc = f"one of {oca_desc}"
    return (
        awst_nodes.ExpressionStatement(
            awst_nodes.AssertExpression(
                condition=condition,
                error_message=f"OnCompletion is not {oca_desc}",
                source_location=location,
            )
        ),
    )


def _map_abi_args(
    arg_types: Sequence[wtypes.WType], location: SourceLocation
) -> Iterable[awst_nodes.Expression]:
    transaction_arg_offset = 0
    incoming_types = []
    for a in arg_types:
        if isinstance(a, wtypes.WGroupTransaction):
            transaction_arg_offset += 1
        else:
            if isinstance(a, wtypes.ARC4Type):
                arc4_type = a
            elif _reference_type_array(a) is not None:
                arc4_type = wtypes.arc4_byte_alias
            else:
                arc4_type = wtype_to_arc4_wtype(a, location)
            incoming_types.append(arc4_type)

    if len(incoming_types) > 15:
        unpacked_types, packed_types = incoming_types[:14], incoming_types[14:]
    else:
        unpacked_types, packed_types = incoming_types, []
    abi_args = [
        app_arg(array_index, arg_wtype, location)
        for array_index, arg_wtype in enumerate(unpacked_types, start=1)
    ]
    if packed_types:
        abi_args.extend(
            awst_nodes.TupleItemExpression(
                base=app_arg(
                    15, wtypes.ARC4Tuple(types=packed_types, source_location=location), location
                ),
                index=tuple_index,
                source_location=location,
            )
            for tuple_index, _ in enumerate(packed_types)
        )
    abi_args.reverse()  # reverse so we can pop off end

    for arg in arg_types:
        if isinstance(arg, wtypes.WGroupTransaction):
            transaction_index = uint64_sub(
                _txn("GroupIndex", wtypes.uint64_wtype, location),
                constant(transaction_arg_offset, location),
                location,
            )
            yield awst_nodes.GroupTransactionReference(
                index=transaction_index, wtype=arg, source_location=location
            )
            transaction_arg_offset -= 1
        else:
            abi_arg = abi_args.pop()
            if (ref_array := _reference_type_array(arg)) is not None:
                uint64_index = _btoi(abi_arg, location)
                yield awst_nodes.IntrinsicCall(
                    op_code="txnas",
                    immediates=[ref_array],
                    stack_args=[uint64_index],
                    wtype=arg,
                    source_location=location,
                )
            else:
                if isinstance(arg, wtypes.StackArray) and is_equivalent_effective_array_encoding(
                    arg, abi_arg.wtype, abi_arg.source_location
                ):
                    abi_arg = awst_nodes.ReinterpretCast(
                        expr=abi_arg, wtype=arg, source_location=abi_arg.source_location
                    )
                elif abi_arg.wtype != arg:
                    abi_arg = awst_nodes.ARC4Decode(
                        value=abi_arg, wtype=arg, source_location=abi_arg.source_location
                    )
                yield abi_arg


def route_abi_methods(
    location: SourceLocation,
    methods: Mapping[md.ARC4ABIMethod, AWSTContractMethodSignature],
) -> awst_nodes.Block:
    method_routing_cases = dict[awst_nodes.Expression, awst_nodes.Block]()
    seen_signatures = set[str]()
    for method, sig in methods.items():
        abi_loc = method.config_location
        abi_args = list(_map_abi_args(sig.parameter_types, location))
        method_result = call(abi_loc, sig, *abi_args)
        match sig.return_type:
            case wtypes.void_wtype:
                call_and_maybe_log = awst_nodes.ExpressionStatement(method_result)
            case wtypes.ARC4Type():
                call_and_maybe_log = log_arc4_result(abi_loc, method_result)
            case _:
                converted_return_type = wtype_to_arc4_wtype(sig.return_type, abi_loc)
                arc4_encoded = awst_nodes.ARC4Encode(
                    value=method_result,
                    wtype=converted_return_type,
                    source_location=method_result.source_location,
                )
                call_and_maybe_log = log_arc4_result(abi_loc, arc4_encoded)

        arc4_signature = method.signature
        if not set_add(seen_signatures, arc4_signature):
            raise CodeError(
                f"Cannot have duplicate ARC-4 method signatures: {arc4_signature}", abi_loc
            )
        method_routing_cases[
            awst_nodes.MethodConstant(source_location=location, value=arc4_signature)
        ] = create_block(
            abi_loc,
            f"{method.name}_route",
            *check_allowed_oca(method.allowed_completion_types, abi_loc),
            *assert_create_state(method),
            call_and_maybe_log,
            approve(abi_loc),
        )
    return create_block(
        location,
        "abi_routing",
        *_maybe_switch(_txn_app_args(0, location), method_routing_cases),
    )


def _maybe_switch(
    value: awst_nodes.Expression, cases: Mapping[awst_nodes.Expression, awst_nodes.Block]
) -> Sequence[awst_nodes.Statement]:
    if not cases:
        return ()
    return [
        awst_nodes.Switch(
            value=value,
            cases=cases,
            default_case=None,
            source_location=value.source_location,
        )
    ]


def create_abi_router(
    contract: awst_nodes.Contract,
    arc4_methods_with_signatures: Mapping[md.ARC4Method, AWSTContractMethodSignature],
) -> awst_nodes.ContractMethod:
    router_location = contract.source_location
    abi_methods = {}
    bare_methods = {}
    for method, sig in arc4_methods_with_signatures.items():
        if isinstance(method, md.ARC4BareMethod):
            bare_methods[method] = sig
        else:
            abi_methods[method] = sig

    abi_routing = route_abi_methods(router_location, abi_methods)
    bare_routing = route_bare_methods(router_location, bare_methods)
    num_app_args = _txn("NumAppArgs", wtypes.uint64_wtype, router_location)
    router = [
        awst_nodes.IfElse(
            condition=_non_zero(num_app_args),
            if_branch=abi_routing,
            else_branch=bare_routing,
            source_location=router_location,
        ),
        reject(router_location),
    ]
    approval_program = awst_nodes.ContractMethod(
        cref=contract.id,
        member_name="__puya_arc4_router__",
        source_location=router_location,
        args=[],
        return_type=wtypes.bool_wtype,
        body=create_block(router_location, None, *router),
        documentation=awst_nodes.MethodDocumentation(),
        arc4_method_config=None,
        inline=True,
    )
    return approval_program


def _reference_type_array(wtype: wtypes.WType) -> str | None:
    match wtype:
        case wtypes.asset_wtype:
            return "Assets"
        case wtypes.account_wtype:
            return "Accounts"
        case wtypes.application_wtype:
            return "Applications"
    return None
