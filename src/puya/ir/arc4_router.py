import typing
from collections.abc import Iterable, Mapping, Sequence

from puyapy.awst_build import intrinsic_factory

from puya import log
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.models import (
    ARC4ABIMethod,
    ARC4ABIMethodConfig,
    ARC4BareMethod,
    ARC4BareMethodConfig,
    ARC4CreateOption,
    ARC4Method,
    ARC4MethodArg,
    ARC4MethodConfig,
    ARC4Returns,
    ContractState,
    OnCompletionAction,
)
from puya.parse import SourceLocation
from puya.utils import set_add

__all__ = [
    "create_abi_router",
    "extract_arc4_methods",
]

logger = log.get_logger(__name__)

ALL_VALID_APPROVAL_ON_COMPLETION_ACTIONS = {
    OnCompletionAction.NoOp,
    OnCompletionAction.OptIn,
    OnCompletionAction.CloseOut,
    OnCompletionAction.UpdateApplication,
    OnCompletionAction.DeleteApplication,
}


def create_block(
    location: SourceLocation, comment: str | None, *stmts: awst_nodes.Statement
) -> awst_nodes.Block:
    return awst_nodes.Block(source_location=location, body=stmts, comment=comment)


def call(
    location: SourceLocation, method: awst_nodes.ContractMethod, *args: awst_nodes.Expression
) -> awst_nodes.SubroutineCallExpression:
    return awst_nodes.SubroutineCallExpression(
        source_location=location,
        wtype=method.return_type,
        target=awst_nodes.ContractMethodTarget(cref=method.cref, member_name=method.member_name),
        args=[awst_nodes.CallArg(name=None, value=arg) for arg in args],
    )


def app_arg(
    index: int,
    wtype: wtypes.WType,
    location: SourceLocation,
) -> awst_nodes.Expression:
    value = intrinsic_factory.txn_app_args(index, location)
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
    return intrinsic_factory.txn("OnCompletion", wtypes.uint64_wtype, location)


def route_bare_methods(
    location: SourceLocation,
    bare_methods: dict[awst_nodes.ContractMethod, ARC4BareMethodConfig],
) -> awst_nodes.Block | None:
    bare_blocks = dict[OnCompletionAction, awst_nodes.Block]()
    for bare_method, config in bare_methods.items():
        bare_location = bare_method.source_location
        bare_block = create_block(
            bare_location,
            bare_method.member_name,
            *assert_create_state(config, config.source_location or bare_location),
            awst_nodes.ExpressionStatement(expr=call(bare_location, bare_method)),
            approve(bare_location),
        )
        for oca in config.allowed_completion_types:
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
    return awst_nodes.ExpressionStatement(intrinsic_factory.log(abi_log, location))


def assert_create_state(
    config: ARC4MethodConfig, location: SourceLocation
) -> Sequence[awst_nodes.Statement]:
    app_id = intrinsic_factory.txn("ApplicationID", wtypes.uint64_wtype, location)
    match config.create:
        case ARC4CreateOption.allow:
            # if create is allowed but not required, we don't need to check anything
            return ()
        case ARC4CreateOption.disallow:
            condition = _non_zero(app_id)
            comment = "is not creating"
        case ARC4CreateOption.require:
            condition = _is_zero(app_id)
            comment = "is creating"
        case invalid:
            typing.assert_never(invalid)
    return [
        awst_nodes.ExpressionStatement(
            expr=intrinsic_factory.assert_(
                condition=condition, comment=comment, source_location=location
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
        case [single_allowed], _:
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
            expr=intrinsic_factory.assert_(
                condition=condition,
                comment=f"OnCompletion is {oca_desc}",
                source_location=location,
            )
        ),
    )


def asset_id_at(
    asset_index: awst_nodes.Expression, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.asset_wtype,
        op_code="txnas",
        immediates=["Assets"],
        stack_args=[asset_index],
    )


def account_at(
    account_index: awst_nodes.Expression, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.account_wtype,
        op_code="txnas",
        immediates=["Accounts"],
        stack_args=[account_index],
    )


def application_at(
    application_index: awst_nodes.Expression, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.application_wtype,
        op_code="txnas",
        immediates=["Applications"],
        stack_args=[application_index],
    )


def current_group_index(location: SourceLocation) -> awst_nodes.Expression:
    return intrinsic_factory.txn("GroupIndex", wtypes.uint64_wtype, location)


def arc4_tuple_index(
    arc4_tuple_expression: awst_nodes.Expression, index: int, location: SourceLocation
) -> awst_nodes.Expression:
    assert isinstance(arc4_tuple_expression.wtype, wtypes.ARC4Tuple)

    return awst_nodes.TupleItemExpression(
        base=arc4_tuple_expression, index=index, source_location=location
    )


def map_abi_args(
    args: Sequence[awst_nodes.SubroutineArgument], location: SourceLocation
) -> Iterable[awst_nodes.Expression]:
    abi_arg_index = 1  # 0th arg is for method selector
    transaction_arg_offset = sum(1 for a in args if isinstance(a.wtype, wtypes.WGroupTransaction))

    non_transaction_args = [a for a in args if not isinstance(a.wtype, wtypes.WGroupTransaction)]
    last_arg: awst_nodes.Expression | None = None
    if len(non_transaction_args) > 15:

        def map_param_wtype_to_arc4_tuple_type(wtype: wtypes.WType) -> wtypes.WType:
            if _has_arc4_equivalent_type(wtype):
                return _avm_to_arc4_equivalent_type(wtype)
            elif _is_reference_type(wtype):
                return wtypes.arc4_byte_alias
            else:
                return wtype

        args_overflow_wtype = wtypes.ARC4Tuple(
            types=[map_param_wtype_to_arc4_tuple_type(a.wtype) for a in non_transaction_args[14:]],
            source_location=location,
        )
        last_arg = app_arg(15, args_overflow_wtype, location)

    def get_arg(index: int, arg_wtype: wtypes.WType) -> awst_nodes.Expression:
        if index < 15:
            return app_arg(index, arg_wtype, location)
        else:
            if last_arg is None:
                raise InternalError("last_arg should not be None if there are more than 15 args")
            return arc4_tuple_index(last_arg, index - 15, location)

    for arg in args:
        match arg.wtype:
            case wtypes.asset_wtype:
                bytes_arg = get_arg(abi_arg_index, wtypes.bytes_wtype)
                asset_index = intrinsic_factory.btoi(bytes_arg, location)
                asset_id = asset_id_at(asset_index, location)
                yield asset_id
                abi_arg_index += 1

            case wtypes.account_wtype:
                bytes_arg = get_arg(abi_arg_index, wtypes.bytes_wtype)
                account_index = intrinsic_factory.btoi(bytes_arg, location)
                account = account_at(account_index, location)
                yield account
                abi_arg_index += 1
            case wtypes.application_wtype:
                bytes_arg = get_arg(abi_arg_index, wtypes.bytes_wtype)
                application_index = intrinsic_factory.btoi(bytes_arg, location)
                application = application_at(application_index, location)
                yield application
                abi_arg_index += 1
            case wtypes.WGroupTransaction() as txn_wtype:
                transaction_index = uint64_sub(
                    current_group_index(location),
                    constant(
                        transaction_arg_offset,
                        location,
                    ),
                    location,
                )
                yield awst_nodes.GroupTransactionReference(
                    index=transaction_index, wtype=txn_wtype, source_location=location
                )
                transaction_arg_offset -= 1
            case _ if _has_arc4_equivalent_type(arg.wtype):
                abi_arg = get_arg(abi_arg_index, _avm_to_arc4_equivalent_type(arg.wtype))
                decoded_abi_arg = _arc4_decode(
                    bytes_arg=abi_arg, target_wtype=arg.wtype, location=location
                )
                yield decoded_abi_arg
                abi_arg_index += 1

            case _:
                abi_arg = get_arg(abi_arg_index, arg.wtype)
                yield abi_arg
                abi_arg_index += 1


def route_abi_methods(
    location: SourceLocation,
    methods: dict[awst_nodes.ContractMethod, ARC4ABIMethodConfig],
) -> awst_nodes.Block:
    method_routing_cases = dict[awst_nodes.Expression, awst_nodes.Block]()
    seen_signatures = set[str]()
    for method, config in methods.items():
        abi_loc = config.source_location or location
        method_result = call(abi_loc, method, *map_abi_args(method.args, location))
        match method.return_type:
            case wtypes.void_wtype:
                call_and_maybe_log = awst_nodes.ExpressionStatement(method_result)
            case wtypes.ARC4Type():
                call_and_maybe_log = log_arc4_result(abi_loc, method_result)
            case _:
                if not _has_arc4_equivalent_type(method.return_type):
                    raise CodeError(
                        f"{method.return_type} is not a valid ABI return type",
                        method.source_location,
                    )
                arc4_encoded = _arc4_encode(method_result)
                call_and_maybe_log = log_arc4_result(abi_loc, arc4_encoded)

        arc4_signature = _get_abi_signature(method, config)
        if not set_add(seen_signatures, arc4_signature):
            raise CodeError(
                f"Cannot have duplicate ARC4 method signatures: {arc4_signature}", abi_loc
            )
        method_routing_cases[
            awst_nodes.MethodConstant(source_location=location, value=arc4_signature)
        ] = create_block(
            abi_loc,
            f"{config.name}_route",
            *check_allowed_oca(config.allowed_completion_types, abi_loc),
            *assert_create_state(config, config.source_location or abi_loc),
            call_and_maybe_log,
            approve(abi_loc),
        )
    return create_block(
        location,
        "abi_routing",
        *_maybe_switch(intrinsic_factory.txn_app_args(0, location), method_routing_cases),
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


def _validate_default_args(
    arc4_methods: Iterable[awst_nodes.ContractMethod],
    known_sources: dict[str, ContractState | awst_nodes.ContractMethod],
) -> None:
    for method in arc4_methods:
        assert isinstance(method.arc4_method_config, ARC4ABIMethodConfig)
        args_by_name = {a.name: a for a in method.args}
        for (
            parameter_name,
            source_name,
        ) in method.arc4_method_config.default_args.items():
            # any invalid parameter matches should have been caught earlier
            parameter = args_by_name[parameter_name]
            param_arc4_type = _wtype_to_arc4(parameter.wtype)
            # special handling for reference types
            match param_arc4_type:
                case "asset" | "application":
                    param_arc4_type = "uint64"
                case "account":
                    param_arc4_type = "address"

            try:
                source = known_sources[source_name]
            except KeyError as ex:
                raise CodeError(
                    f"'{source_name}' is not a known state or method attribute",
                    method.source_location,
                ) from ex

            match source:
                case awst_nodes.ContractMethod(
                    arc4_method_config=ARC4ABIMethodConfig() as abi_method_config,
                    args=args,
                    return_type=return_type,
                ):
                    if OnCompletionAction.NoOp not in abi_method_config.allowed_completion_types:
                        raise CodeError(
                            f"'{source_name}' does not allow no_op on completion calls",
                            method.source_location,
                        )
                    if abi_method_config.create == ARC4CreateOption.require:
                        raise CodeError(
                            f"'{source_name}' can only be used for create calls",
                            method.source_location,
                        )
                    if not abi_method_config.readonly:
                        raise CodeError(
                            f"'{source_name}' is not readonly",
                            method.source_location,
                        )
                    if args:
                        raise CodeError(
                            f"'{source_name}' does not take zero arguments",
                            method.source_location,
                        )
                    if return_type is wtypes.void_wtype:
                        raise CodeError(
                            f"'{source_name}' does not provide a value",
                            method.source_location,
                        )
                    if _wtype_to_arc4(return_type) != param_arc4_type:
                        raise CodeError(
                            f"'{source_name}' does not provide '{param_arc4_type}' type",
                            method.source_location,
                        )
                case ContractState(storage_type=storage_type):
                    if (
                        storage_type is AVMType.uint64
                        # storage can provide an int to types <= uint64
                        # TODO: check what ATC does with ufixed, see if it can be added
                        and (param_arc4_type == "byte" or param_arc4_type.startswith("uint"))
                    ) or (
                        storage_type is AVMType.bytes
                        # storage can provide fixed byte arrays
                        and (
                            (param_arc4_type.startswith("byte[") and param_arc4_type != "byte[]")
                            or param_arc4_type == "address"
                        )
                    ):
                        pass
                    else:
                        raise CodeError(
                            f"'{source_name}' cannot provide '{param_arc4_type}' type",
                            method.source_location,
                        )
                case _:
                    raise InternalError(
                        f"Unhandled known default argument source type {type(source).__name__}",
                        method.source_location,
                    )


def extract_arc4_methods(
    arc4_methods_with_configs: dict[awst_nodes.ContractMethod, ARC4MethodConfig],
    *,
    global_state: Mapping[str, ContractState],
    local_state: Mapping[str, ContractState],
) -> list[ARC4Method]:
    abi_methods = {}
    bare_methods = {}
    known_sources: dict[str, ContractState | awst_nodes.ContractMethod] = {
        **global_state,
        **local_state,
    }
    for m, arc4_config in arc4_methods_with_configs.items():
        assert arc4_config is m.arc4_method_config
        if isinstance(arc4_config, ARC4BareMethodConfig):
            bare_methods[m] = arc4_config
        elif isinstance(arc4_config, ARC4ABIMethodConfig):
            abi_methods[m] = arc4_config
            known_sources[m.member_name] = m
        else:
            typing.assert_never(arc4_config)

    _validate_default_args(abi_methods.keys(), known_sources)

    arc4_method_metadata = list[ARC4Method]()
    for m, bare_method_config in bare_methods.items():
        arc4_method_metadata.append(
            ARC4BareMethod(
                desc=m.documentation.description,
                config=bare_method_config,
            )
        )
    for m, abi_method_config in abi_methods.items():
        arc4_method_metadata.append(
            ARC4ABIMethod(
                name=m.member_name,
                desc=m.documentation.description,
                args=[
                    ARC4MethodArg(
                        name=a.name,
                        type_=_wtype_to_arc4(a.wtype),
                        desc=m.documentation.args.get(a.name),
                    )
                    for a in m.args
                ],
                returns=ARC4Returns(
                    desc=m.documentation.returns,
                    type_=_wtype_to_arc4(m.return_type),
                ),
                config=abi_method_config,
            )
        )
    return arc4_method_metadata


def create_abi_router(
    contract: awst_nodes.ContractFragment,
    arc4_methods_with_configs: dict[awst_nodes.ContractMethod, ARC4MethodConfig],
) -> awst_nodes.ContractMethod:
    router_location = contract.source_location
    abi_methods = {}
    bare_methods = {}
    arc4_method_metadata = list[ARC4Method]()
    for m, arc4_config in arc4_methods_with_configs.items():
        doc = m.documentation
        assert arc4_config is m.arc4_method_config
        if isinstance(arc4_config, ARC4BareMethodConfig):
            bare_methods[m] = arc4_config
            metadata: ARC4Method = ARC4BareMethod(desc=doc.description, config=arc4_config)
        elif isinstance(arc4_config, ARC4ABIMethodConfig):
            abi_methods[m] = arc4_config
            metadata = ARC4ABIMethod(
                name=m.member_name,
                desc=doc.description,
                args=[
                    ARC4MethodArg(
                        name=a.name, type_=_wtype_to_arc4(a.wtype), desc=doc.args.get(a.name)
                    )
                    for a in m.args
                ],
                returns=ARC4Returns(desc=doc.returns, type_=_wtype_to_arc4(m.return_type)),
                config=arc4_config,
            )
        else:
            typing.assert_never(arc4_config)
        arc4_method_metadata.append(metadata)

    abi_routing = route_abi_methods(router_location, abi_methods)
    bare_routing = route_bare_methods(router_location, bare_methods)
    num_app_args = intrinsic_factory.txn("NumAppArgs", wtypes.uint64_wtype, router_location)
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
    )
    return approval_program


def _arc4_encode(base: awst_nodes.Expression) -> awst_nodes.Expression:
    """encode, with special handling of native tuples"""
    location = base.source_location
    target_wtype = _avm_to_arc4_equivalent_type(base.wtype)
    value = base
    match base.wtype:
        case wtypes.WTuple(types=types):
            if not isinstance(base, awst_nodes.SingleEvaluation):
                base = awst_nodes.SingleEvaluation(base)
            encoded_items = [
                _maybe_arc4_encode(
                    awst_nodes.TupleItemExpression(base=base, index=i, source_location=location)
                )
                for i, t in enumerate(types)
            ]
            value = awst_nodes.TupleExpression.from_items(encoded_items, location)
    return awst_nodes.ARC4Encode(value=value, wtype=target_wtype, source_location=location)


def _maybe_arc4_encode(item: awst_nodes.Expression) -> awst_nodes.Expression:
    """Encode as arc4 if wtype is not already an arc4 encoded type"""
    if isinstance(item.wtype, wtypes.ARC4Type):
        return item
    return _arc4_encode(item)


def _arc4_decode(
    bytes_arg: awst_nodes.Expression, target_wtype: wtypes.WType, location: SourceLocation
) -> awst_nodes.Expression:
    """decode, with special handling of native tuples"""
    match bytes_arg.wtype, target_wtype:
        case wtypes.ARC4Tuple(types=arc4_item_types), wtypes.WTuple(types=target_item_types):
            decode_expression = awst_nodes.ARC4Decode(
                value=bytes_arg,
                wtype=wtypes.WTuple(arc4_item_types, location),
                source_location=location,
            )
            if arc4_item_types == target_item_types:
                return decode_expression
            decoded = awst_nodes.SingleEvaluation(decode_expression)
            decoded_items = [
                _maybe_arc4_decode(
                    awst_nodes.TupleItemExpression(
                        base=decoded, index=idx, source_location=location
                    ),
                    target_item_wtype,
                )
                for idx, target_item_wtype in enumerate(target_item_types)
            ]
            return awst_nodes.TupleExpression.from_items(decoded_items, location)
        case _:
            return awst_nodes.ARC4Decode(
                value=bytes_arg, wtype=target_wtype, source_location=location
            )


def _maybe_arc4_decode(
    item: awst_nodes.Expression, target_wtype: wtypes.WType
) -> awst_nodes.Expression:
    if item.wtype == target_wtype:
        return item
    return _arc4_decode(item, target_wtype, item.source_location)


def _get_abi_signature(subroutine: awst_nodes.ContractMethod, config: ARC4ABIMethodConfig) -> str:
    arg_types = [_wtype_to_arc4(a.wtype, a.source_location) for a in subroutine.args]
    return_type = _wtype_to_arc4(subroutine.return_type, subroutine.source_location)
    return f"{config.name}({','.join(arg_types)}){return_type}"


def _wtype_to_arc4(wtype: wtypes.WType, loc: SourceLocation | None = None) -> str:
    match wtype:
        case wtypes.ARC4Type(arc4_name=arc4_name):
            return arc4_name
        case (
            wtypes.void_wtype
            | wtypes.asset_wtype
            | wtypes.account_wtype
            | wtypes.application_wtype
            | wtypes.uint64_wtype
            | wtypes.bool_wtype
            | wtypes.string_wtype
        ):
            return wtype.name
        case wtypes.biguint_wtype:
            return "uint512"
        case wtypes.bytes_wtype:
            return "byte[]"
        case wtypes.WGroupTransaction(transaction_type=transaction_type):
            return transaction_type.name if transaction_type else "txn"
        case wtypes.WTuple(types=types):
            item_types = ",".join([_wtype_to_arc4(item) for item in types])
            return f"({item_types})"
        case _:
            raise CodeError(f"not an ARC4 type or native equivalent: {wtype}", loc)


def _is_reference_type(wtype: wtypes.WType) -> bool:
    return wtype in (wtypes.asset_wtype, wtypes.account_wtype, wtypes.application_wtype)


def _has_arc4_equivalent_type(wtype: wtypes.WType) -> bool:
    """
    Checks if a non-arc4 encoded type has an arc4 equivalent
    """
    if wtype in (
        wtypes.bool_wtype,
        wtypes.uint64_wtype,
        wtypes.bytes_wtype,
        wtypes.biguint_wtype,
        wtypes.string_wtype,
    ):
        return True

    match wtype:
        case wtypes.WTuple(types=types):
            return all(
                (_has_arc4_equivalent_type(t) or isinstance(t, wtypes.ARC4Type)) for t in types
            )
    return False


def _avm_to_arc4_equivalent_type(wtype: wtypes.WType) -> wtypes.ARC4Type:
    if wtype is wtypes.bool_wtype:
        return wtypes.arc4_bool_wtype
    if wtype is wtypes.uint64_wtype:
        return wtypes.ARC4UIntN(n=64, decode_type=wtype, source_location=None)
    if wtype is wtypes.biguint_wtype:
        return wtypes.ARC4UIntN(n=512, decode_type=wtype, source_location=None)
    if wtype is wtypes.bytes_wtype:
        return wtypes.ARC4DynamicArray(
            element_type=wtypes.arc4_byte_alias, decode_type=wtype, source_location=None
        )
    if wtype is wtypes.string_wtype:
        return wtypes.arc4_string_alias
    if isinstance(wtype, wtypes.WTuple):
        return wtypes.ARC4Tuple(
            types=(
                t if isinstance(t, wtypes.ARC4Type) else _avm_to_arc4_equivalent_type(t)
                for t in wtype.types
            ),
            source_location=None,
        )
    raise InternalError(f"{wtype} does not have an arc4 equivalent type")
