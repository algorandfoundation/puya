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
from puya.ir.arc4_types import wtype_to_arc4_wtype
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


def _create_block(
    location: SourceLocation, comment: str | None, *stmts: awst_nodes.Statement
) -> awst_nodes.Block:
    return awst_nodes.Block(source_location=location, body=stmts, comment=comment)


def _call(
    location: SourceLocation, sig: AWSTContractMethodSignature, *args: awst_nodes.Expression
) -> awst_nodes.SubroutineCallExpression:
    return awst_nodes.SubroutineCallExpression(
        target=sig.target,
        args=[awst_nodes.CallArg(name=None, value=arg) for arg in args],
        wtype=sig.return_type,
        source_location=location,
    )


def _app_arg(
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


def _return(value: bool, location: SourceLocation) -> awst_nodes.Statement:  # noqa: FBT001
    return awst_nodes.ExpressionStatement(
        awst_nodes.IntrinsicCall(
            op_code="return",
            immediates=[],
            stack_args=[awst_nodes.BoolConstant(value=value, source_location=location)],
            wtype=wtypes.void_wtype,
            source_location=location,
        )
    )


def _reject(location: SourceLocation) -> awst_nodes.Statement:
    return _return(False, location)  # noqa: FBT003


def _approve(location: SourceLocation) -> awst_nodes.Statement:
    return _return(True, location)  # noqa: FBT003


def _on_completion(location: SourceLocation) -> awst_nodes.Expression:
    return _txn("OnCompletion", wtypes.uint64_wtype, location)


def _assign_true_or_approve(
    match_var: awst_nodes.VarExpression | None, loc: SourceLocation
) -> awst_nodes.Statement:
    if match_var is None:
        return _approve(loc)
    return awst_nodes.AssignmentStatement(
        target=match_var,
        value=awst_nodes.BoolConstant(value=True, source_location=loc),
        source_location=loc,
    )


def _route_bare_methods(
    location: SourceLocation,
    bare_methods: Mapping[md.ARC4BareMethod, AWSTContractMethodSignature],
    *,
    assign_true_on_match: awst_nodes.VarExpression | None,
) -> awst_nodes.Block:
    assert bare_methods, "route_bare_methods called with no bare methods"
    if len(bare_methods) == 1:
        method, sig = dict(bare_methods).popitem()
        bare_location = method.config_location
        return _create_block(
            bare_location,
            sig.target.member_name,
            *_check_allowed_oca_and_create(method),
            awst_nodes.ExpressionStatement(expr=_call(bare_location, sig)),
            _assign_true_or_approve(assign_true_on_match, bare_location),
        )

    bare_blocks = dict[OnCompletionAction, awst_nodes.Block]()
    for method, sig in bare_methods.items():
        bare_location = method.config_location
        bare_block = _create_block(
            bare_location,
            sig.target.member_name,
            *_assert_create_state(method.create, bare_location),
            awst_nodes.ExpressionStatement(expr=_call(bare_location, sig)),
            _assign_true_or_approve(assign_true_on_match, bare_location),
        )
        for oca in method.allowed_completion_types:
            if bare_blocks.setdefault(oca, bare_block) is not bare_block:
                logger.error(
                    f"cannot have multiple bare methods handling the same "
                    f"OnCompletionAction: {oca.name}",
                    location=bare_location,
                )
    return _create_block(
        location,
        "bare_routing",
        awst_nodes.Switch(
            value=_on_completion(location),
            cases={
                _oca_constant(oca, location): block
                for oca in OnCompletionAction
                if (block := bare_blocks.get(oca))
            },
            default_case=None,
            source_location=location,
        ),
    )


def _log_arc4_result(
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


def _app_id(loc: SourceLocation) -> awst_nodes.Expression:
    return _txn("ApplicationID", wtypes.uint64_wtype, loc)


def _assert_create_state(
    create: awst_nodes.ARC4CreateOption, loc: SourceLocation
) -> Sequence[awst_nodes.Statement]:
    app_id = _app_id(loc)
    match create:
        case awst_nodes.ARC4CreateOption.allow:
            # if create is allowed but not required, we don't need to check anything
            return ()
        case awst_nodes.ARC4CreateOption.disallow:
            condition = _neq_uint64(app_id, 0, loc)
            error_message = "can only call when not creating"
        case awst_nodes.ARC4CreateOption.require:
            condition = _eq_uint64(app_id, 0, loc)
            error_message = "can only call when creating"
        case invalid:
            typing.assert_never(invalid)
    return (_assert_statement(condition, error_message, loc),)


def _constant(value: int, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.UInt64Constant(value=value, source_location=location)


def _oca_constant(oca: OnCompletionAction, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.UInt64Constant(
        value=oca.value,
        teal_alias=oca.name,
        source_location=location,
    )


def _left_shift(value: awst_nodes.Expression, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.UInt64BinaryOperation(
        source_location=location,
        left=_constant(1, location),
        op=awst_nodes.UInt64BinaryOperator.lshift,
        right=value,
    )


def _bit_and(
    lhs: awst_nodes.Expression, rhs: awst_nodes.Expression, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.UInt64BinaryOperation(
        source_location=location,
        left=lhs,
        op=awst_nodes.UInt64BinaryOperator.bit_and,
        right=rhs,
    )


def _uint64_sub(
    lhs: awst_nodes.Expression, rhs: awst_nodes.Expression, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.UInt64BinaryOperation(
        source_location=location,
        left=lhs,
        op=awst_nodes.UInt64BinaryOperator.sub,
        right=rhs,
    )


def _bit_packed_oca(
    allowed_oca: Iterable[OnCompletionAction], location: SourceLocation
) -> awst_nodes.Expression:
    """Returns an integer constant, where each bit corresponding to an OnCompletionAction is
    set to 1 if that action is allowed. This allows comparing a transaction's on completion value
    against a set of allowed actions using a bitwise and op"""
    bit_packed_value = 0
    for value in allowed_oca:
        bit_packed_value |= 1 << value.value
    return _constant(bit_packed_value, location)


def _compare_uint64(
    lhs: awst_nodes.Expression,
    rhs: int | OnCompletionAction,
    operator: awst_nodes.NumericComparison,
    location: SourceLocation,
) -> awst_nodes.Expression:
    if isinstance(rhs, OnCompletionAction):
        rhs_expr = _oca_constant(rhs, location)
    else:
        rhs_expr = _constant(rhs, location)
    return awst_nodes.NumericComparisonExpression(
        lhs=lhs, rhs=rhs_expr, operator=operator, source_location=location
    )


def _eq_uint64(
    lhs: awst_nodes.Expression, rhs: int | OnCompletionAction, location: SourceLocation
) -> awst_nodes.Expression:
    return _compare_uint64(lhs, rhs, awst_nodes.NumericComparison.eq, location)


def _neq_uint64(
    lhs: awst_nodes.Expression, rhs: int | OnCompletionAction, location: SourceLocation
) -> awst_nodes.Expression:
    return _compare_uint64(lhs, rhs, awst_nodes.NumericComparison.ne, location)


def _check_allowed_oca_and_create(method: md.ARC4Method) -> Sequence[awst_nodes.Statement]:
    loc = method.config_location

    allowed_ocas = method.allowed_completion_types
    not_allowed_ocas = sorted(
        a for a in ALL_VALID_APPROVAL_ON_COMPLETION_ACTIONS if a not in allowed_ocas
    )
    conditions = list[tuple[str, awst_nodes.Expression]]()
    # if all possible actions are allowed, don't need to check
    if not_allowed_ocas:
        oca_expr = _on_completion(loc)
        match allowed_ocas, not_allowed_ocas:
            case [[single_allowed], _]:
                oca_condition = _eq_uint64(oca_expr, single_allowed, loc)
            case [_, [single_disallowed]]:
                oca_condition = _neq_uint64(oca_expr, single_disallowed, loc)
            case _:
                oca_condition = _bit_and(
                    _left_shift(oca_expr, loc), _bit_packed_oca(allowed_ocas, loc), loc
                )
        oca_desc = ", ".join(a.name for a in allowed_ocas)
        if len(allowed_ocas) > 1:
            oca_desc = f"one of {oca_desc}"
        conditions.append((f"OnCompletion must be {oca_desc}", oca_condition))

    app_id = _app_id(loc)
    match method.create:
        case awst_nodes.ARC4CreateOption.allow:
            # if create is allowed but not required, we don't need to check anything
            pass
        case awst_nodes.ARC4CreateOption.disallow:
            conditions.append(("can only call when not creating", _neq_uint64(app_id, 0, loc)))
        case awst_nodes.ARC4CreateOption.require:
            conditions.append(("can only call when creating", _eq_uint64(app_id, 0, loc)))
        case invalid:
            typing.assert_never(invalid)

    match conditions:
        case []:
            return ()
        case [(error_message, condition)]:
            pass
        case _:
            error_messages, conditions_ = zip(*conditions, strict=True)
            error_message = " && ".join(error_messages)
            condition = awst_nodes.IntrinsicCall(
                source_location=loc,
                wtype=wtypes.bool_wtype,
                op_code="&&",
                immediates=[],
                stack_args=conditions_,
            )

    return (_assert_statement(condition, error_message, loc),)


def _assert_statement(
    condition: awst_nodes.Expression, error_message: str, location: SourceLocation
) -> awst_nodes.Statement:
    return awst_nodes.ExpressionStatement(
        awst_nodes.AssertExpression(
            condition=condition,
            error_message=error_message,
            source_location=location,
        )
    )


def _map_abi_args(
    arg_types: Sequence[wtypes.WType], location: SourceLocation, *, use_reference_alias: bool
) -> Iterable[awst_nodes.Expression]:
    transaction_arg_offset = 0
    incoming_types = []
    for a in arg_types:
        if isinstance(a, wtypes.WGroupTransaction):
            transaction_arg_offset += 1
        else:
            if isinstance(a, wtypes.ARC4Type):
                arc4_type = a
            elif use_reference_alias and _reference_type_array(a) is not None:
                arc4_type = wtypes.arc4_byte_alias
            else:
                arc4_type = wtype_to_arc4_wtype(a, location)
            incoming_types.append(arc4_type)

    if len(incoming_types) > 15:
        unpacked_types, packed_types = incoming_types[:14], incoming_types[14:]
    else:
        unpacked_types, packed_types = incoming_types, []
    abi_args = [
        _app_arg(array_index, arg_wtype, location)
        for array_index, arg_wtype in enumerate(unpacked_types, start=1)
    ]
    if packed_types:
        abi_args.extend(
            awst_nodes.TupleItemExpression(
                base=_app_arg(
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
            transaction_index = _uint64_sub(
                _txn("GroupIndex", wtypes.uint64_wtype, location),
                _constant(transaction_arg_offset, location),
                location,
            )
            yield awst_nodes.GroupTransactionReference(
                index=transaction_index, wtype=arg, source_location=location
            )
            transaction_arg_offset -= 1
        else:
            abi_arg = abi_args.pop()
            if use_reference_alias and (ref_array := _reference_type_array(arg)) is not None:
                uint64_index = _btoi(abi_arg, location)
                yield awst_nodes.IntrinsicCall(
                    op_code="txnas",
                    immediates=[ref_array],
                    stack_args=[uint64_index],
                    wtype=arg,
                    source_location=location,
                )
            else:
                if abi_arg.wtype != arg:
                    abi_arg = awst_nodes.ARC4Decode(
                        value=abi_arg, wtype=arg, source_location=abi_arg.source_location
                    )
                yield abi_arg


def _build_abi_wrapper(
    method: md.ARC4ABIMethod, sig: AWSTContractMethodSignature, *, exit_success: bool
) -> awst_nodes.Subroutine:
    abi_loc = method.config_location
    use_reference_alias = method.resource_encoding == "index"
    abi_args = list(
        _map_abi_args(sig.parameter_types, abi_loc, use_reference_alias=use_reference_alias)
    )
    method_result = _call(abi_loc, sig, *abi_args)
    match sig.return_type:
        case wtypes.void_wtype:
            call_and_maybe_log = awst_nodes.ExpressionStatement(method_result)
        case wtypes.ARC4Type():
            call_and_maybe_log = _log_arc4_result(abi_loc, method_result)
        case _:
            converted_return_type = wtype_to_arc4_wtype(sig.return_type, abi_loc)
            arc4_encoded = awst_nodes.ARC4Encode(
                value=method_result,
                wtype=converted_return_type,
                source_location=method_result.source_location,
            )
            call_and_maybe_log = _log_arc4_result(abi_loc, arc4_encoded)
    body: list[awst_nodes.Statement] = [call_and_maybe_log]
    if exit_success:
        body.append(_approve(abi_loc))
    qualified_name = ".".join((sig.target.cref, sig.target.member_name))
    wrapper_method = awst_nodes.Subroutine(
        args=[],
        return_type=wtypes.void_wtype,
        body=awst_nodes.Block(body=body, source_location=abi_loc),
        documentation=awst_nodes.MethodDocumentation(),
        name=sig.target.member_name,
        id=f"{qualified_name}[routing]",
        source_location=abi_loc,
    )
    return wrapper_method


def _check_for_duplicates(methods: Mapping[md.ARC4ABIMethod, AWSTContractMethodSignature]) -> None:
    seen_signatures = set[str]()
    duplicate_errors = [
        CodeError(
            f"Cannot have duplicate ARC-4 method signatures: {method.signature}",
            method.config_location,
        )
        for method in methods
        if not set_add(seen_signatures, method.signature)
    ]
    if duplicate_errors:
        raise ExceptionGroup("ARC-4 signature errors", duplicate_errors)


def _create_abi_switch(
    router_location: SourceLocation,
    cases: Iterable[tuple[md.ARC4ABIMethod, awst_nodes.Subroutine]],
    *,
    check_oca_and_create: bool,
    assign_true_on_match: awst_nodes.VarExpression | None,
) -> Sequence[awst_nodes.Switch]:
    case_blocks = dict[awst_nodes.Expression, awst_nodes.Block]()
    for method, method_wrapper in cases:
        abi_loc = method.config_location
        method_const = awst_nodes.MethodConstant(
            source_location=router_location, value=method.signature
        )
        stmts = list[awst_nodes.Statement]()
        if check_oca_and_create:
            stmts = list(_check_allowed_oca_and_create(method))
        stmts.append(
            awst_nodes.ExpressionStatement(
                awst_nodes.SubroutineCallExpression(
                    target=awst_nodes.SubroutineID(method_wrapper.id),
                    args=[],
                    wtype=wtypes.void_wtype,
                    source_location=abi_loc,
                )
            )
        )
        if assign_true_on_match is not None:
            stmts.append(
                awst_nodes.AssignmentStatement(
                    target=assign_true_on_match,
                    value=awst_nodes.BoolConstant(value=True, source_location=abi_loc),
                    source_location=abi_loc,
                )
            )
        call_block = _create_block(abi_loc, f"{method.name}_route", *stmts)
        case_blocks[method_const] = call_block
    if not case_blocks:
        return ()
    switch = awst_nodes.Switch(
        source_location=router_location,
        value=_txn_app_args(0, router_location),
        cases=case_blocks,
        default_case=None,
    )
    return (switch,)


def _route_abi_methods(
    router_location: SourceLocation,
    methods: Mapping[md.ARC4ABIMethod, AWSTContractMethodSignature],
    *,
    assign_true_on_match: awst_nodes.VarExpression | None,
) -> tuple[awst_nodes.Block, list[awst_nodes.Subroutine]]:
    _check_for_duplicates(methods)

    arc4_wrapper_methods = list[awst_nodes.Subroutine]()
    no_op_only_routing_methods = {}
    other_routing_methods = {}
    for method, sig in methods.items():
        wrapper_method = _build_abi_wrapper(method, sig, exit_success=assign_true_on_match is None)
        arc4_wrapper_methods.append(wrapper_method)
        match method:
            case md.ARC4ABIMethod(allowed_completion_types=[OnCompletionAction.NoOp]):
                no_op_only_routing_methods[method] = wrapper_method
            case _:
                other_routing_methods[method] = wrapper_method

    no_op_by_create = dict[
        awst_nodes.ARC4CreateOption, list[tuple[md.ARC4ABIMethod, awst_nodes.Subroutine]]
    ]()
    if len(no_op_only_routing_methods) == 1:
        other_routing_methods.update(no_op_only_routing_methods)
        no_op_only_routing_methods.clear()
    else:
        for method, wrapper_method in no_op_only_routing_methods.items():
            no_op_by_create.setdefault(method.create, []).append((method, wrapper_method))

    if not no_op_by_create:
        no_op_routing: Sequence[awst_nodes.Statement] = ()
    else:
        no_op_routing = (
            _assert_statement(
                _eq_uint64(
                    _on_completion(router_location), OnCompletionAction.NoOp, router_location
                ),
                "OnCompletion must be NoOp",
                router_location,
            ),
            *_create_abi_switch(
                router_location,
                no_op_by_create.get(awst_nodes.ARC4CreateOption.allow, []),
                check_oca_and_create=False,
                assign_true_on_match=assign_true_on_match,
            ),
            awst_nodes.IfElse(
                source_location=router_location,
                condition=_neq_uint64(_app_id(router_location), 0, router_location),
                if_branch=_create_block(
                    router_location,
                    "call_NoOp",
                    *_create_abi_switch(
                        router_location,
                        no_op_by_create.get(awst_nodes.ARC4CreateOption.disallow, []),
                        check_oca_and_create=False,
                        assign_true_on_match=assign_true_on_match,
                    ),
                ),
                else_branch=_create_block(
                    router_location,
                    "create_NoOp",
                    *_create_abi_switch(
                        router_location,
                        no_op_by_create.get(awst_nodes.ARC4CreateOption.require, []),
                        check_oca_and_create=False,
                        assign_true_on_match=assign_true_on_match,
                    ),
                ),
            ),
        )

    abi_routing_block = _create_block(
        router_location,
        "abi_routing",
        *_create_abi_switch(
            router_location,
            other_routing_methods.items(),
            check_oca_and_create=True,
            assign_true_on_match=assign_true_on_match,
        ),
        *no_op_routing,
    )
    return abi_routing_block, arc4_wrapper_methods


def create_abi_router(
    contract: awst_nodes.Contract,
    arc4_methods_with_signatures: Mapping[md.ARC4Method, AWSTContractMethodSignature],
    *,
    can_exit_early: bool,
) -> tuple[awst_nodes.ContractMethod, Sequence[awst_nodes.Subroutine]]:
    router_location = contract.source_location
    abi_methods = {}
    bare_methods = {}
    for method, sig in arc4_methods_with_signatures.items():
        if isinstance(method, md.ARC4BareMethod):
            bare_methods[method] = sig
        else:
            abi_methods[method] = sig

    match_var = awst_nodes.VarExpression(
        name="%did_match_routing",
        wtype=wtypes.bool_wtype,
        source_location=router_location,
    )
    abi_routing, abi_wrapper_methods = _route_abi_methods(
        router_location,
        abi_methods,
        assign_true_on_match=None if can_exit_early else match_var,
    )
    router: list[awst_nodes.Statement]
    if not bare_methods:
        router = [*abi_routing.body]
    else:
        bare_routing = _route_bare_methods(
            router_location,
            bare_methods,
            assign_true_on_match=None if can_exit_early else match_var,
        )
        value = _txn("NumAppArgs", wtypes.uint64_wtype, router_location)
        router = [
            awst_nodes.IfElse(
                condition=_neq_uint64(value, 0, router_location),
                if_branch=abi_routing,
                else_branch=bare_routing,
                source_location=router_location,
            )
        ]
    if can_exit_early:
        router.append(_reject(router_location))
    else:
        router = [
            awst_nodes.AssignmentStatement(
                target=match_var,
                value=awst_nodes.BoolConstant(value=False, source_location=router_location),
                source_location=router_location,
            ),
            *router,
            awst_nodes.ReturnStatement(
                value=match_var,
                source_location=router_location,
            ),
        ]
    approval_program = awst_nodes.ContractMethod(
        cref=contract.id,
        member_name="__puya_arc4_router__",
        source_location=router_location,
        args=[],
        return_type=wtypes.bool_wtype,
        body=_create_block(router_location, None, *router),
        documentation=awst_nodes.MethodDocumentation(),
        arc4_method_config=None,
        inline=True,
    )
    return approval_program, abi_wrapper_methods


def _reference_type_array(wtype: wtypes.WType) -> str | None:
    match wtype:
        case wtypes.asset_wtype:
            return "Assets"
        case wtypes.account_wtype:
            return "Accounts"
        case wtypes.application_wtype:
            return "Applications"
    return None
