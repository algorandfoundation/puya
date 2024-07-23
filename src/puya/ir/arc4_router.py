import typing
from collections.abc import Iterable, Mapping, Sequence

from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.wtypes import (
    ARC4DynamicArray,
    ARC4Tuple,
    ARC4Type,
    ARC4UIntN,
    WGroupTransaction,
    WTuple,
    WType,
    account_wtype,
    application_wtype,
    arc4_bool_wtype,
    arc4_byte_alias,
    arc4_string_alias,
    asset_wtype,
    biguint_wtype,
    bool_wtype,
    bytes_wtype,
    string_wtype,
    uint64_wtype,
)
from puya.awst_build import intrinsic_factory
from puya.awst_build.eb.transaction import check_transaction_type
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
from puya.parse import SourceLocation, parse_docstring

__all__ = [
    "create_abi_router",
    "create_default_clear_state",
]
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
    location: SourceLocation, function: awst_nodes.Function, *args: awst_nodes.Expression
) -> awst_nodes.SubroutineCallExpression:
    return awst_nodes.SubroutineCallExpression(
        source_location=location,
        wtype=function.return_type,
        target=awst_nodes.InstanceSubroutineTarget(name=function.name),
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


def has_app_id(location: SourceLocation) -> awst_nodes.Expression:
    return intrinsic_factory.txn(
        "ApplicationID",
        wtypes.bool_wtype,  # treat as bool
        location,
    )


def method_selector(location: SourceLocation) -> awst_nodes.Expression:
    return intrinsic_factory.txn_app_args(0, location)


def has_app_args(location: SourceLocation) -> awst_nodes.Expression:
    return intrinsic_factory.txn(
        "NumAppArgs",
        wtypes.bool_wtype,  # treat as bool
        location,
    )


def reject(location: SourceLocation) -> awst_nodes.Statement:
    return awst_nodes.ExpressionStatement(
        expr=intrinsic_factory.assert_(
            source_location=location,
            condition=awst_nodes.BoolConstant(source_location=location, value=False),
            comment="reject transaction",
        )
    )


def approve(location: SourceLocation) -> awst_nodes.ReturnStatement:
    return awst_nodes.ReturnStatement(
        source_location=location,
        value=awst_nodes.BoolConstant(value=True, source_location=location),
    )


def on_completion(location: SourceLocation) -> awst_nodes.Expression:
    return intrinsic_factory.txn("OnCompletion", wtypes.uint64_wtype, location)


def create_oca_switch(
    block_mapping: dict[OnCompletionAction, awst_nodes.Block],
    default_case: awst_nodes.Block,
    location: SourceLocation,
) -> awst_nodes.Switch:
    return awst_nodes.Switch(
        source_location=location,
        value=on_completion(location),
        cases={
            awst_nodes.UInt64Constant(value=oca.value, source_location=location): block
            for oca, block in block_mapping.items()
            if block is not default_case
        },
        default_case=default_case,
    )


def route_bare_methods(
    location: SourceLocation,
    bare_methods: dict[awst_nodes.ContractMethod, ARC4BareMethodConfig],
    *,
    add_create: bool,
) -> awst_nodes.Block | None:
    if not bare_methods and not add_create:
        return None
    err_block = create_block(
        location,
        "reject_bare_on_completion",
        reject(location),
    )
    bare_blocks = {oca: err_block for oca in OnCompletionAction}
    for bare_method, config in bare_methods.items():
        bare_location = bare_method.source_location
        bare_block = create_block(
            bare_location,
            bare_method.name,
            *assert_create_state(config, config.source_location or bare_location),
            awst_nodes.ExpressionStatement(expr=call(bare_location, bare_method)),
            approve(bare_location),
        )
        for oca in config.allowed_completion_types:
            if bare_blocks[oca] is not err_block:
                raise CodeError(
                    f"Cannot have multiple bare methods handling the same "
                    f"OnCompletionAction: {oca.name}",
                    bare_location,
                )
            bare_blocks[oca] = bare_block
    if add_create:
        if bare_blocks[OnCompletionAction.NoOp] is not err_block:
            raise CodeError(
                "Application has no methods that can be called to create the contract, "
                "but does have a NoOp bare method, so one couldn't be inserted. "
                "In order to allow creating the contract add either an @abimethod or @baremethod"
                'decorated method with create="require" or create="allow"',
                location,
            )
        bare_blocks[OnCompletionAction.NoOp] = create_block(
            location,
            "create",
            *assert_create_state(
                ARC4BareMethodConfig(create=ARC4CreateOption.require, source_location=location),
                location,
            ),
            approve(location),
        )

    return create_block(
        location,
        "bare_routing",
        create_oca_switch(bare_blocks, err_block, location),
    )


def log_arc4_compatible_result(
    location: SourceLocation, result_expression: awst_nodes.Expression
) -> awst_nodes.ExpressionStatement:
    arc4_encoded = _arc4_encode(
        result_expression, _avm_to_arc4_equivalent_type(result_expression.wtype), location
    )
    return log_arc4_result(location, arc4_encoded)


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
    existing_app = has_app_id(location)
    match config.create:
        case ARC4CreateOption.allow:
            # if create is allowed but not required, we don't need to check anything
            return ()
        case ARC4CreateOption.disallow:
            condition: awst_nodes.Expression = existing_app
            comment = "is not creating"
        case ARC4CreateOption.require:
            condition = awst_nodes.Not(expr=existing_app, source_location=location)
            comment = "is creating"
        case invalid:
            typing.assert_never(invalid)
    return [
        awst_nodes.ExpressionStatement(
            expr=intrinsic_factory.assert_(
                condition=condition,
                comment=comment,
                source_location=location,
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


def as_bool(expr: awst_nodes.Expression, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.ReinterpretCast(
        expr=expr,
        wtype=wtypes.bool_wtype,
        source_location=location,
    )


def check_allowed_oca(
    allowed_ocas: Sequence[OnCompletionAction], location: SourceLocation
) -> Sequence[awst_nodes.Statement]:
    if set(allowed_ocas) == ALL_VALID_APPROVAL_ON_COMPLETION_ACTIONS:
        # all actions are allowed, don't need to check
        return ()
    not_allowed_ocas = sorted(
        a for a in ALL_VALID_APPROVAL_ON_COMPLETION_ACTIONS if a not in allowed_ocas
    )
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
            condition = as_bool(
                bit_and(
                    left_shift(on_completion(location), location),
                    bit_packed_oca(allowed_ocas, location),
                    location,
                ),
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
    transaction_arg_offset = sum(1 for a in args if isinstance(a.wtype, WGroupTransaction))

    non_transaction_args = [a for a in args if not isinstance(a.wtype, WGroupTransaction)]
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
            [map_param_wtype_to_arc4_tuple_type(a.wtype) for a in non_transaction_args[14:]],
            location,
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
                yield check_transaction_type(transaction_index, txn_wtype, location)
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
    if not methods:
        return create_block(location, "reject_abi_methods", reject(location))
    method_routing_cases = dict[awst_nodes.Expression, awst_nodes.Block]()
    seen_signatures = set[str]()
    for method, config in methods.items():
        abi_loc = config.source_location or location
        method_result = call(abi_loc, method, *map_abi_args(method.args, location))
        match method.return_type:
            case wtypes.void_wtype:
                call_and_maybe_log = awst_nodes.ExpressionStatement(method_result)
            case _ if isinstance(method.return_type, ARC4Type):
                call_and_maybe_log = log_arc4_result(abi_loc, method_result)
            case _ if _has_arc4_equivalent_type(method.return_type):
                call_and_maybe_log = log_arc4_compatible_result(abi_loc, method_result)
            case _:
                raise CodeError(
                    f"{method.return_type} is not a valid ABI return type", method.source_location
                )

        method_routing_block = create_block(
            abi_loc,
            f"{config.name}_route",
            *check_allowed_oca(config.allowed_completion_types, abi_loc),
            *assert_create_state(config, config.source_location or abi_loc),
            call_and_maybe_log,
            approve(abi_loc),
        )
        arc4_signature = _get_abi_signature(method, config)
        if arc4_signature in seen_signatures:
            raise CodeError(
                f"Cannot have duplicate ARC4 method signatures: {arc4_signature}", abi_loc
            )
        seen_signatures.add(arc4_signature)
        method_selector_value = awst_nodes.MethodConstant(
            source_location=location, value=arc4_signature
        )
        method_routing_cases[method_selector_value] = method_routing_block
    return create_block(
        location,
        "abi_routing",
        awst_nodes.Switch(
            source_location=location,
            value=method_selector(location),
            cases=method_routing_cases,
            default_case=None,
        ),
        reject(location),
    )


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


def create_abi_router(
    contract: awst_nodes.ContractFragment,
    arc4_methods_with_configs: dict[awst_nodes.ContractMethod, ARC4MethodConfig],
    *,
    global_state: Mapping[str, ContractState],
    local_state: Mapping[str, ContractState],
) -> tuple[awst_nodes.ContractMethod, list[ARC4Method]]:
    abi_methods = {}
    bare_methods = {}
    has_create = False
    known_sources: dict[str, ContractState | awst_nodes.ContractMethod] = {
        **global_state,
        **local_state,
    }
    for m, arc4_config in arc4_methods_with_configs.items():
        assert arc4_config is m.arc4_method_config
        if arc4_config.create != ARC4CreateOption.disallow:
            has_create = True
        if isinstance(arc4_config, ARC4BareMethodConfig):
            bare_methods[m] = arc4_config
        elif isinstance(arc4_config, ARC4ABIMethodConfig):
            abi_methods[m] = arc4_config
            known_sources[m.name] = m
        else:
            typing.assert_never(arc4_config)
    router_location = contract.source_location
    if bare_methods or not has_create:
        router: list[awst_nodes.Statement] = [
            awst_nodes.IfElse(
                source_location=router_location,
                condition=has_app_args(router_location),
                if_branch=route_abi_methods(router_location, abi_methods),
                else_branch=route_bare_methods(
                    router_location, bare_methods, add_create=not has_create
                ),
            )
        ]
    else:
        router = list(route_abi_methods(router_location, abi_methods).body)

    _validate_default_args(abi_methods.keys(), known_sources)

    docs = {s: parse_docstring(s.docstring) for s in arc4_methods_with_configs}

    arc4_method_metadata = list[ARC4Method]()
    for m, bare_method_config in bare_methods.items():
        arc4_method_metadata.append(
            ARC4BareMethod(
                desc=docs[m].description,
                config=bare_method_config,
            )
        )
    for m, abi_method_config in abi_methods.items():
        arc4_method_metadata.append(
            ARC4ABIMethod(
                name=m.name,
                desc=docs[m].description,
                args=[
                    ARC4MethodArg(
                        name=a.name,
                        type_=_wtype_to_arc4(a.wtype),
                        desc=docs[m].args.get(a.name),
                    )
                    for a in m.args
                ],
                returns=ARC4Returns(
                    desc=docs[m].returns,
                    type_=_wtype_to_arc4(m.return_type),
                ),
                config=abi_method_config,
            )
        )
    if not has_create:
        arc4_method_metadata.append(
            ARC4BareMethod(
                config=ARC4BareMethodConfig(
                    create=ARC4CreateOption.require, source_location=router_location
                ),
                desc=None,
            )
        )

    approval_program = awst_nodes.ContractMethod(
        module_name=contract.module_name,
        class_name=contract.name,
        name="approval_program",
        source_location=router_location,
        args=[],
        return_type=wtypes.bool_wtype,
        body=create_block(router_location, "abi_bare_routing", *router),
        docstring=None,
        arc4_method_config=None,
    )
    return approval_program, arc4_method_metadata


def create_default_clear_state(contract: awst_nodes.ContractFragment) -> awst_nodes.ContractMethod:
    # equivalent to:
    # def clear_state_program(self) -> bool:
    #   return True
    return awst_nodes.ContractMethod(
        module_name=contract.module_name,
        class_name=contract.name,
        name="clear_state_program",
        source_location=contract.source_location,
        args=[],
        return_type=wtypes.bool_wtype,
        body=create_block(
            contract.source_location,
            None,
            approve(contract.source_location),
        ),
        docstring=None,
        arc4_method_config=None,
    )


def _arc4_encode(
    base: awst_nodes.Expression, target_wtype: wtypes.ARC4Type, location: SourceLocation
) -> awst_nodes.Expression:
    """encode, with special handling of native tuples"""
    match base.wtype:
        case wtypes.WTuple(types=types):

            base_temp = (
                base
                if isinstance(base, awst_nodes.SingleEvaluation)
                else awst_nodes.SingleEvaluation(base)
            )

            return awst_nodes.ARC4Encode(
                source_location=location,
                value=awst_nodes.TupleExpression.from_items(
                    items=[
                        _maybe_arc4_encode(
                            awst_nodes.TupleItemExpression(
                                base=base_temp,
                                index=i,
                                source_location=location,
                            ),
                            t,
                            location,
                        )
                        for i, t in enumerate(types)
                    ],
                    location=location,
                ),
                wtype=target_wtype,
            )

        case _:
            return awst_nodes.ARC4Encode(
                source_location=location,
                value=base,
                wtype=target_wtype,
            )


def _maybe_arc4_encode(
    item: awst_nodes.Expression, wtype: wtypes.WType, location: SourceLocation
) -> awst_nodes.Expression:
    """Encode as arc4 if wtype is not already an arc4 encoded type"""
    if isinstance(wtype, ARC4Type):
        return item
    return _arc4_encode(item, _avm_to_arc4_equivalent_type(wtype), location)


def _arc4_decode(
    bytes_arg: awst_nodes.Expression,
    target_wtype: wtypes.WType,
    location: SourceLocation,
) -> awst_nodes.Expression:
    """decode, with special handling of native tuples"""
    match bytes_arg.wtype:
        case wtypes.ARC4DynamicArray(
            element_type=wtypes.ARC4UIntN(n=8)
        ) if target_wtype == wtypes.bytes_wtype:
            return intrinsic_factory.extract(bytes_arg, start=2, loc=location)
        case wtypes.ARC4Tuple(types=tuple_types):
            decode_expression = awst_nodes.ARC4Decode(
                source_location=location,
                wtype=wtypes.WTuple(tuple_types, location),
                value=bytes_arg,
            )
            assert isinstance(
                target_wtype, wtypes.WTuple
            ), "Target wtype must be a WTuple when decoding ARC4Tuple"
            if all(
                target == current
                for target, current in zip(target_wtype.types, tuple_types, strict=True)
            ):
                return decode_expression
            decoded = awst_nodes.SingleEvaluation(decode_expression)
            return awst_nodes.TupleExpression.from_items(
                items=[
                    _maybe_arc4_decode(
                        awst_nodes.TupleItemExpression(
                            base=decoded,
                            index=i,
                            source_location=location,
                        ),
                        target_wtype=t_t,
                        current_wtype=t_c,
                        location=location,
                    )
                    for i, (t_c, t_t) in enumerate(
                        zip(tuple_types, target_wtype.types, strict=True)
                    )
                ],
                location=location,
            )

        case _:
            return awst_nodes.ARC4Decode(
                source_location=location,
                wtype=target_wtype,
                value=bytes_arg,
            )


def _maybe_arc4_decode(
    item: awst_nodes.Expression,
    *,
    current_wtype: wtypes.WType,
    target_wtype: wtypes.WType,
    location: SourceLocation,
) -> awst_nodes.Expression:
    if current_wtype == target_wtype:
        return item
    return _arc4_decode(item, target_wtype, location)


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


def _is_reference_type(wtype: WType) -> bool:
    return wtype in (asset_wtype, account_wtype, application_wtype)


def _has_arc4_equivalent_type(wtype: WType) -> bool:
    """
    Checks if a non-arc4 encoded type has an arc4 equivalent
    """
    if wtype in (bool_wtype, uint64_wtype, bytes_wtype, biguint_wtype, string_wtype):
        return True

    match wtype:
        case WTuple(types=types):
            return all((_has_arc4_equivalent_type(t) or isinstance(t, ARC4Type)) for t in types)
    return False


def _avm_to_arc4_equivalent_type(wtype: WType) -> ARC4Type:
    if wtype is bool_wtype:
        return arc4_bool_wtype
    if wtype is uint64_wtype:
        return ARC4UIntN(64, decode_type=wtype, source_location=None)
    if wtype is biguint_wtype:
        return ARC4UIntN(512, decode_type=wtype, source_location=None)
    if wtype is bytes_wtype:
        return ARC4DynamicArray(
            element_type=arc4_byte_alias, native_type=wtype, source_location=None
        )
    if wtype is string_wtype:
        return arc4_string_alias
    if isinstance(wtype, WTuple):
        return ARC4Tuple(
            types=(
                t if isinstance(t, ARC4Type) else _avm_to_arc4_equivalent_type(t)
                for t in wtype.types
            ),
            source_location=None,
        )
    raise InternalError(f"{wtype} does not have an arc4 equivalent type")
