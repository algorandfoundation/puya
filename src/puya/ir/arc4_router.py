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
    location: SourceLocation,
    comment: str | None,
    *stmts: awst_nodes.Statement,
    label: str | None = None,
) -> awst_nodes.Block:
    return awst_nodes.Block(
        source_location=location,
        body=stmts,
        comment=comment,
        label=awst_nodes.Label(label) if label is not None else None,
    )


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


def _is_zero(value: awst_nodes.Expression) -> awst_nodes.Expression:
    location = value.source_location
    return awst_nodes.NumericComparisonExpression(
        lhs=value,
        rhs=_constant(0, location),
        operator=awst_nodes.NumericComparison.eq,
        source_location=location,
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


def _constant(value: int, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.UInt64Constant(value=value, source_location=location)


def _left_shift(value: awst_nodes.Expression, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.UInt64BinaryOperation(
        source_location=location,
        left=value,
        op=awst_nodes.UInt64BinaryOperator.lshift,
        right=_constant(1, location),
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


def _uint64_add(
    lhs: awst_nodes.Expression, rhs: awst_nodes.Expression, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.UInt64BinaryOperation(
        source_location=location,
        left=lhs,
        op=awst_nodes.UInt64BinaryOperator.add,
        right=rhs,
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
    method: md.ARC4ABIMethod, sig: AWSTContractMethodSignature
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
    qualified_name = ".".join((sig.target.cref, sig.target.member_name))
    wrapper_method = awst_nodes.Subroutine(
        args=[],
        return_type=wtypes.void_wtype,
        body=awst_nodes.Block(
            body=[call_and_maybe_log, _approve(abi_loc)],
            source_location=abi_loc,
        ),
        documentation=awst_nodes.MethodDocumentation(),
        name=sig.target.member_name,
        id=f"{qualified_name}[routing]",
        source_location=abi_loc,
    )
    return wrapper_method


@attrs.define
class _ABIScenario:
    method: md.ARC4ABIMethod
    sig: AWSTContractMethodSignature
    wrapper: awst_nodes.Subroutine


@attrs.define
class _ScenarioData:
    bare_method: tuple[md.ARC4BareMethod, AWSTContractMethodSignature] | None = None
    abi_methods: list[_ABIScenario] = attrs.field(factory=list)


def _route_methods(
    router_location: SourceLocation,
    arc4_methods_with_signatures: Mapping[md.ARC4Method, AWSTContractMethodSignature],
) -> tuple[awst_nodes.Block, list[awst_nodes.Subroutine]]:
    seen_signatures = set[str]()

    allowed_methods_by_scenario = dict[tuple[OnCompletionAction, bool], _ScenarioData]()
    synthetic_methods = list[awst_nodes.Subroutine]()
    for method, sig in arc4_methods_with_signatures.items():
        if isinstance(method, md.ARC4BareMethod):
            match method.create:
                case awst_nodes.ARC4CreateOption.allow:
                    creates = [True, False]
                case awst_nodes.ARC4CreateOption.disallow:
                    creates = [False]
                case awst_nodes.ARC4CreateOption.require:
                    creates = [True]
                case unexpected:
                    typing.assert_never(unexpected)
            for oca in method.allowed_completion_types:
                for create in creates:
                    sd = allowed_methods_by_scenario.setdefault((oca, create), _ScenarioData())
                    if sd.bare_method is not None:
                        logger.error(
                            f"cannot have multiple bare methods handling the same "
                            f"OnCompletionAction: {oca.name}",
                            location=method.config_location,
                        )
                    else:
                        sd.bare_method = (method, sig)
        else:
            if not set_add(seen_signatures, method.signature):
                raise CodeError(
                    f"Cannot have duplicate ARC-4 method signatures: {method.signature}",
                    method.config_location,
                )
            wrapper_method = _build_abi_wrapper(method, sig)
            synthetic_methods.append(wrapper_method)
            match method.create:
                case awst_nodes.ARC4CreateOption.allow:
                    creates = [True, False]
                case awst_nodes.ARC4CreateOption.disallow:
                    creates = [False]
                case awst_nodes.ARC4CreateOption.require:
                    creates = [True]
                case unexpected:
                    typing.assert_never(unexpected)
            abi_data = _ABIScenario(method, sig, wrapper_method)
            for oca in method.allowed_completion_types:
                for create in creates:
                    allowed_methods_by_scenario.setdefault(
                        (oca, create), _ScenarioData()
                    ).abi_methods.append(abi_data)

    cmp = _uint64_add(
        awst_nodes.ReinterpretCast(
            expr=awst_nodes.Not(
                expr=_txn("ApplicationID", wtypes.bool_wtype, router_location),
                source_location=router_location,
            ),
            wtype=wtypes.uint64_wtype,
            source_location=router_location,
        ),
        _left_shift(_txn("OnCompletion", wtypes.uint64_wtype, router_location), router_location),
        router_location,
    )
    scenarios = {}
    not_implemented_label = awst_nodes.Label("*NOT_IMPLEMENTED")
    not_implemented = awst_nodes.Block(
        source_location=router_location,
        label=not_implemented_label,
        body=[
            awst_nodes.ExpressionStatement(
                awst_nodes.AssertExpression(
                    source_location=router_location,
                    condition=None,
                    error_message="The requested action is not implemented in this contract."
                    " Are you using the correct OnComplete? Did you set your app ID?",
                )
            )
        ],
    )
    for oca in OnCompletionAction:
        for create in (False, True):
            scenario = allowed_methods_by_scenario.get((oca, create))
            scenario_stmts: Sequence[awst_nodes.Statement]
            if scenario is None:
                scenario_stmts = [
                    awst_nodes.Goto(source_location=router_location, target=not_implemented_label),
                ]
            else:
                scenario_abi_method_routes = dict[awst_nodes.Expression, awst_nodes.Block]()
                for abi_data in scenario.abi_methods:
                    wrapper_method = abi_data.wrapper
                    abi_loc = abi_data.method.config_location
                    scenario_abi_method_routes[
                        awst_nodes.MethodConstant(
                            source_location=router_location, value=abi_data.method.signature
                        )
                    ] = _create_block(
                        abi_loc,
                        f"{abi_data.method.name}_route",
                        awst_nodes.ExpressionStatement(
                            awst_nodes.SubroutineCallExpression(
                                target=awst_nodes.SubroutineID(wrapper_method.id),
                                args=[],
                                wtype=wtypes.void_wtype,
                                source_location=router_location,
                            )
                        ),
                    )

                scenario_abi_switch = [
                    *_maybe_switch(_txn_app_args(0, router_location), scenario_abi_method_routes),
                    awst_nodes.ExpressionStatement(
                        awst_nodes.AssertExpression(
                            source_location=router_location,
                            condition=None,
                            error_message=f"this contract does not implement the given ABI method for"
                            f" {'create' if create else 'call'} {oca.name}",
                        )
                    ),
                ]
                if scenario.bare_method is None:
                    scenario_stmts = scenario_abi_switch
                else:
                    bare_method, bare_sig = scenario.bare_method
                    bare_location = bare_method.config_location
                    bare_block = _create_block(
                        bare_location,
                        bare_sig.target.member_name,
                        awst_nodes.ExpressionStatement(expr=_call(bare_location, bare_sig)),
                        _approve(bare_location),
                    )
                    scenario_stmts = [
                        awst_nodes.IfElse(
                            condition=_is_zero(
                                _txn("NumAppArgs", wtypes.uint64_wtype, router_location)
                            ),
                            if_branch=bare_block,
                            else_branch=_create_block(router_location, None, *scenario_abi_switch),
                            source_location=router_location,
                        )
                    ]
            compare_constant: awst_nodes.Expression = _constant(
                (oca.value << 1) + (1 if create else 0), router_location
            )
            scenarios[compare_constant] = _create_block(
                router_location,
                None,
                *scenario_stmts,
                label=f"{'create' if create else 'call'}_{oca.name}",
            )

    abi_routing_block = _create_block(
        router_location, "router", *_maybe_switch(cmp, scenarios, default=not_implemented)
    )
    return abi_routing_block, synthetic_methods


def _maybe_switch(
    value: awst_nodes.Expression,
    cases: Mapping[awst_nodes.Expression, awst_nodes.Block],
    *,
    default: awst_nodes.Block | None = None,
) -> Sequence[awst_nodes.Statement]:
    if default is None and not cases:
        return ()
    return [
        awst_nodes.Switch(
            value=value,
            cases=cases,
            default_case=default,
            source_location=value.source_location,
        )
    ]


def create_abi_router(
    contract: awst_nodes.Contract,
    arc4_methods_with_signatures: Mapping[md.ARC4Method, AWSTContractMethodSignature],
) -> tuple[awst_nodes.ContractMethod, Sequence[awst_nodes.Subroutine]]:
    router_location = contract.source_location

    router, abi_wrapper_methods = _route_methods(router_location, arc4_methods_with_signatures)
    approval_program = awst_nodes.ContractMethod(
        cref=contract.id,
        member_name="__puya_arc4_router__",
        source_location=router_location,
        args=[],
        return_type=wtypes.bool_wtype,
        body=router,
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
