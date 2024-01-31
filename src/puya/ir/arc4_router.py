import itertools
from typing import Iterable, Sequence

from puya.arc4_util import get_abi_signature, wtype_to_arc4
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import NumericComparison, NumericComparisonExpression, UInt64Constant
from puya.awst_build.eb.transaction import check_transaction_type
from puya.awst_build.utils import TemporaryAssignmentExpr, create_temporary_assignment
from puya.errors import CodeError, InternalError
from puya.metadata import (
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
    location: SourceLocation, description: str | None, *stmts: awst_nodes.Statement
) -> awst_nodes.Block:
    return awst_nodes.Block(source_location=location, body=stmts, description=description)


def call(
    location: SourceLocation, function: awst_nodes.Function, *args: awst_nodes.Expression
) -> awst_nodes.SubroutineCallExpression:
    return awst_nodes.SubroutineCallExpression(
        source_location=location,
        wtype=function.return_type,
        target=awst_nodes.InstanceSubroutineTarget(name=function.name),
        args=[awst_nodes.CallArg(name=None, value=arg) for arg in args],
    )


def load_abi_arg(
    index: int,
    wtype: wtypes.WType,
    location: SourceLocation,
) -> awst_nodes.IntrinsicCall:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtype,
        op_code="txna",
        immediates=["ApplicationArgs", index],
    )


def btoi(bytes_arg: awst_nodes.Expression, location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.uint64_wtype,
        op_code="btoi",
        stack_args=[bytes_arg],
    )


def arc4_encode(
    base: awst_nodes.Expression, target_wtype: wtypes.WType, location: SourceLocation
) -> awst_nodes.Expression:
    match base.wtype:
        case wtypes.bytes_wtype:
            base_temp = create_temporary_assignment(base, location)

            length = awst_nodes.IntrinsicCall(
                source_location=location,
                op_code="substring",
                immediates=[6, 8],
                wtype=wtypes.bytes_wtype,
                stack_args=[
                    awst_nodes.IntrinsicCall(
                        source_location=location,
                        op_code="itob",
                        stack_args=[
                            awst_nodes.IntrinsicCall.bytes_len(base_temp.define, location)
                        ],
                        wtype=wtypes.bytes_wtype,
                    )
                ],
            )
            return awst_nodes.ReinterpretCast(
                source_location=location,
                wtype=wtypes.ARC4DynamicArray.from_element_type(
                    wtypes.ARC4UIntN.from_scale(8, alias="byte")
                ),
                expr=awst_nodes.IntrinsicCall(
                    source_location=location,
                    op_code="concat",
                    stack_args=[length, base_temp.read],
                    wtype=wtypes.bytes_wtype,
                ),
            )
        case wtypes.WTuple(types=types):
            base_temp = create_temporary_assignment(base, location)

            return awst_nodes.ARC4Encode(
                source_location=location,
                value=awst_nodes.TupleExpression.from_items(
                    items=[
                        arc4_encode(
                            awst_nodes.TupleItemExpression(
                                base=base_temp.define if i == 0 else base_temp.read,
                                index=i,
                                source_location=location,
                            ),
                            wtypes.avm_to_arc4_equivalent_type(t),
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


def arc4_decode(
    bytes_arg: awst_nodes.Expression,
    target_wtype: wtypes.WType,
    location: SourceLocation,
    *,
    decode_nested_items: bool = False,
) -> awst_nodes.Expression:
    match bytes_arg.wtype:
        case wtypes.ARC4DynamicArray(
            element_type=wtypes.ARC4UIntN(n=8)
        ) if target_wtype == wtypes.bytes_wtype:
            return awst_nodes.IntrinsicCall(
                wtype=wtypes.bytes_wtype,
                op_code="extract",
                immediates=[2, 0],
                source_location=location,
                stack_args=[
                    awst_nodes.ReinterpretCast(
                        expr=bytes_arg, wtype=wtypes.bytes_wtype, source_location=location
                    )
                ],
            )
        case wtypes.ARC4Tuple(types=tuple_types):
            decode_expression = awst_nodes.ARC4Decode(
                source_location=location,
                wtype=wtypes.WTuple.from_types(tuple_types),
                value=bytes_arg,
            )
            if not decode_nested_items:
                return decode_expression
            decoded = create_temporary_assignment(
                decode_expression,
                location=location,
            )
            return awst_nodes.TupleExpression.from_items(
                items=[
                    arc4_decode(
                        awst_nodes.TupleItemExpression(
                            base=decoded.define if i == 0 else decoded.read,
                            index=i,
                            source_location=location,
                        ),
                        wtypes.arc4_to_avm_equivalent_wtype(t),
                        location,
                    )
                    for i, t in enumerate(tuple_types)
                ],
                location=location,
            )

        case _:
            return awst_nodes.ARC4Decode(
                source_location=location,
                wtype=target_wtype,
                value=bytes_arg,
            )


def has_app_id(location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.bool_wtype,  # treat as bool
        op_code="txn",
        immediates=["ApplicationID"],
    )


def method_selector(location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.bytes_wtype,
        op_code="txna",
        immediates=["ApplicationArgs", 0],
    )


def has_app_args(location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.bool_wtype,  # treat as bool
        op_code="txn",
        immediates=["NumAppArgs"],
    )


def reject(location: SourceLocation) -> awst_nodes.Statement:
    return awst_nodes.AssertStatement(
        source_location=location,
        condition=awst_nodes.BoolConstant(source_location=location, value=False),
        comment="reject transaction",
    )


def approve(location: SourceLocation) -> awst_nodes.ReturnStatement:
    return awst_nodes.ReturnStatement(
        source_location=location,
        value=awst_nodes.BoolConstant(value=True, source_location=location),
    )


def on_completion(location: SourceLocation) -> awst_nodes.Expression:
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.uint64_wtype,
        op_code="txn",
        immediates=["OnCompletion"],
    )


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
    bare_methods: dict[awst_nodes.ContractMethod, ARC4MethodConfig],
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
            *assert_create_state(config),
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
                'decorated method with create=True or create="allow"',
                location,
            )
        else:
            bare_blocks[OnCompletionAction.NoOp] = create_block(
                location,
                "create",
                *assert_create_state(
                    ARC4MethodConfig(
                        name="", source_location=location, is_bare=True, require_create=True
                    )
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
    arc4_encoded = arc4_encode(
        result_expression, wtypes.avm_to_arc4_equivalent_type(result_expression.wtype), location
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
    return awst_nodes.ExpressionStatement(
        awst_nodes.IntrinsicCall(
            source_location=location,
            wtype=wtypes.void_wtype,
            op_code="log",
            stack_args=[abi_log],
        )
    )


def assert_create_state(config: ARC4MethodConfig) -> Sequence[awst_nodes.AssertStatement]:
    if config.allow_create:  # if create is allowed, we don't need to check anything
        return ()
    location = config.source_location
    existing_app = has_app_id(location)
    return (
        awst_nodes.AssertStatement(
            condition=awst_nodes.Not(expr=existing_app, source_location=location)
            if config.require_create
            else existing_app,
            comment="is creating" if config.require_create else "is not creating",
            source_location=location,
        ),
    )


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
            condition: awst_nodes.Expression = NumericComparisonExpression(
                lhs=on_completion(location),
                rhs=UInt64Constant(
                    source_location=location,
                    value=single_allowed.value,
                    teal_alias=single_allowed.name,
                ),
                operator=NumericComparison.eq,
                source_location=location,
            )
        case _, [single_disallowed]:
            condition = NumericComparisonExpression(
                lhs=on_completion(location),
                rhs=UInt64Constant(
                    source_location=location,
                    value=single_disallowed.value,
                    teal_alias=single_disallowed.name,
                ),
                operator=NumericComparison.ne,
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
        awst_nodes.AssertStatement(
            condition=condition,
            comment=f"OnCompletion is {oca_desc}",
            source_location=location,
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
    return awst_nodes.IntrinsicCall(
        source_location=location,
        wtype=wtypes.uint64_wtype,
        op_code="txn",
        immediates=["GroupIndex"],
        stack_args=[],
    )


def tuple_item(
    tuple_expression: awst_nodes.Expression, index: int, location: SourceLocation
) -> awst_nodes.Expression:
    return awst_nodes.TupleItemExpression(
        source_location=location, base=tuple_expression, index=index
    )


def map_abi_args(
    args: Sequence[awst_nodes.SubroutineArgument], location: SourceLocation
) -> Iterable[awst_nodes.Expression]:
    abi_arg_index = 1  # 0th arg is for method selector
    transaction_arg_offset = sum(1 for a in args if wtypes.is_transaction_type(a.wtype))

    non_transaction_args = [a for a in args if not wtypes.is_transaction_type(a.wtype)]
    decoded_args: TemporaryAssignmentExpr | None = None
    if len(non_transaction_args) > 15:

        def map_param_wtype_to_arc4_tuple_type(wtype: wtypes.WType) -> wtypes.WType:
            if wtypes.has_arc4_equivalent_type(wtype):
                return wtypes.avm_to_arc4_equivalent_type(wtype)
            elif wtypes.is_reference_type(wtype):
                return wtypes.ARC4UIntN.from_scale(8)
            else:
                return wtype

        args_overflow_wtype = wtypes.ARC4Tuple.from_types(
            [map_param_wtype_to_arc4_tuple_type(a.wtype) for a in non_transaction_args[14:]]
        )
        last_arg = load_abi_arg(15, args_overflow_wtype, location)
        decoded_args = create_temporary_assignment(
            value=arc4_decode(
                last_arg, wtypes.WTuple.from_types(args_overflow_wtype.types), location
            ),
            location=location,
        )

    def get_arg(index: int, arg_wtype: wtypes.WType) -> awst_nodes.Expression:
        if index < 15:
            return load_abi_arg(index, arg_wtype, location)
        elif index == 15:
            if decoded_args is None:
                return load_abi_arg(15, arg_wtype, location)
            return tuple_item(decoded_args.define, 0, location)
        else:
            if decoded_args is None:
                raise InternalError(
                    "Decoded args should not be None if there are more than 15 args"
                )
            return tuple_item(decoded_args.read, index - 15, location)

    for arg in args:
        match arg.wtype:
            case wtypes.asset_wtype:
                bytes_arg = get_arg(abi_arg_index, arg.wtype)
                asset_index = btoi(bytes_arg, location)
                asset_id = asset_id_at(asset_index, location)
                yield asset_id
                abi_arg_index += 1

            case wtypes.account_wtype:
                bytes_arg = get_arg(abi_arg_index, arg.wtype)
                account_index = btoi(bytes_arg, location)
                account = account_at(account_index, location)
                yield account
                abi_arg_index += 1
            case wtypes.application_wtype:
                bytes_arg = get_arg(abi_arg_index, arg.wtype)
                application_index = btoi(bytes_arg, location)
                application = application_at(application_index, location)
                yield application
                abi_arg_index += 1
            case wtypes.WTransaction() as txn_wtype:
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
            case _ if wtypes.has_arc4_equivalent_type(arg.wtype):
                abi_arg = get_arg(abi_arg_index, wtypes.avm_to_arc4_equivalent_type(arg.wtype))
                decoded_abi_arg = arc4_decode(
                    bytes_arg=abi_arg,
                    target_wtype=arg.wtype,
                    location=location,
                    decode_nested_items=True,
                )
                yield decoded_abi_arg
                abi_arg_index += 1

            case _:
                abi_arg = get_arg(abi_arg_index, arg.wtype)
                yield abi_arg
                abi_arg_index += 1


def route_abi_methods(
    location: SourceLocation, methods: dict[awst_nodes.ContractMethod, ARC4MethodConfig]
) -> awst_nodes.Block:
    method_routing_cases = dict[awst_nodes.Expression, awst_nodes.Block]()
    seen_signatures = set[str]()
    for method, config in methods.items():
        abi_loc = config.source_location
        method_result = call(abi_loc, method, *map_abi_args(method.args, location))
        match method.return_type:
            case wtypes.void_wtype:
                call_and_maybe_log = awst_nodes.ExpressionStatement(method_result)
            case _ if wtypes.is_arc4_encoded_type(method.return_type):
                call_and_maybe_log = log_arc4_result(abi_loc, method_result)
            case _ if wtypes.has_arc4_equivalent_type(method.return_type):
                call_and_maybe_log = log_arc4_compatible_result(abi_loc, method_result)
            case _:
                raise CodeError(
                    f"{method.return_type} is not a valid ABI return type", method.source_location
                )

        method_routing_block = create_block(
            abi_loc,
            f"{config.name}_route",
            *check_allowed_oca(config.allowed_completion_types, abi_loc),
            *assert_create_state(config),
            call_and_maybe_log,
            approve(abi_loc),
        )
        arc4_signature = get_abi_signature(method, config)
        if arc4_signature in seen_signatures:
            raise CodeError(
                f"Cannot have duplicate ARC4 method signatures: {arc4_signature}", abi_loc
            )
        seen_signatures.add(arc4_signature)
        method_selector_value = awst_nodes.MethodConstant(
            source_location=abi_loc, value=arc4_signature
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
    )


def _validate_default_args(
    arc4_methods: Iterable[awst_nodes.ContractMethod],
    known_sources: dict[str, ContractState | awst_nodes.ContractMethod],
) -> None:
    for method in arc4_methods:
        assert method.abimethod_config
        args_by_name = {a.name: a for a in method.args}
        for default_arg in method.abimethod_config.default_args:
            # any invalid parameter matches should have been caught earlier
            parameter = args_by_name[default_arg.parameter]
            param_arc4_type = wtype_to_arc4(parameter.wtype)
            # special handling for reference types
            match param_arc4_type:
                case "asset" | "application":
                    param_arc4_type = "uint64"
                case "account":
                    param_arc4_type = "address"

            try:
                source = known_sources[default_arg.source]
            except KeyError as ex:
                raise CodeError(
                    f"'{default_arg.source}' is not a known state or method attribute",
                    method.source_location,
                ) from ex

            match source:
                case awst_nodes.ContractMethod(
                    abimethod_config=ARC4MethodConfig() as abimethod_config,
                    args=args,
                    return_type=return_type,
                ):
                    if OnCompletionAction.NoOp not in abimethod_config.allowed_completion_types:
                        raise CodeError(
                            f"'{default_arg.source}' does not allow no_op on completion calls",
                            method.source_location,
                        )
                    if abimethod_config.require_create:
                        raise CodeError(
                            f"'{default_arg.source}' can only be used for create calls",
                            method.source_location,
                        )
                    if not abimethod_config.readonly:
                        raise CodeError(
                            f"'{default_arg.source}' is not readonly",
                            method.source_location,
                        )
                    if args:
                        raise CodeError(
                            f"'{default_arg.source}' does not take zero arguments",
                            method.source_location,
                        )
                    if return_type is wtypes.void_wtype:
                        raise CodeError(
                            f"'{default_arg.source}' does not provide a value",
                            method.source_location,
                        )
                    if wtype_to_arc4(return_type) != param_arc4_type:
                        raise CodeError(
                            f"'{default_arg.source}' does not provide '{param_arc4_type}' type",
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
                            f"'{default_arg.source}' cannot provide '{param_arc4_type}' type",
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
    global_state: list[ContractState],
    local_state: list[ContractState],
) -> tuple[awst_nodes.ContractMethod, list[ARC4Method]]:
    abi_methods = {}
    bare_methods = {}
    has_create = False
    for m, abi_config in arc4_methods_with_configs.items():
        assert abi_config is m.abimethod_config
        if abi_config.allow_create or abi_config.require_create:
            has_create = True
        if abi_config.is_bare:
            bare_methods[m] = abi_config
        else:
            abi_methods[m] = abi_config
    router_location = contract.source_location
    router = awst_nodes.IfElse(
        source_location=router_location,
        condition=has_app_args(router_location),
        if_branch=route_abi_methods(router_location, abi_methods),
        else_branch=route_bare_methods(router_location, bare_methods, add_create=not has_create),
    )

    known_sources: dict[str, ContractState | awst_nodes.ContractMethod] = {
        s.name: s for s in itertools.chain(global_state, local_state)
    }
    for method in arc4_methods_with_configs:
        known_sources[method.name] = method
    _validate_default_args(arc4_methods_with_configs.keys(), known_sources)

    docs = {s: parse_docstring(s.docstring) for s in arc4_methods_with_configs}

    arc4_method_metadata = [
        ARC4Method(
            name=m.name,
            desc=docs[m].description,
            args=[
                ARC4MethodArg(
                    name=a.name,
                    type_=wtype_to_arc4(a.wtype),
                    desc=docs[m].args.get(a.name),
                )
                for a in m.args
            ],
            returns=ARC4Returns(
                desc=docs[m].returns,
                type_=wtype_to_arc4(m.return_type),
            ),
            config=abi_config,
        )
        for m, abi_config in arc4_methods_with_configs.items()
    ]
    if not has_create:
        arc4_method_metadata.append(
            ARC4Method(
                name="",
                desc=None,
                args=[],
                returns=ARC4Returns(type_="void", desc=None),
                config=ARC4MethodConfig(
                    source_location=router_location,
                    name="",
                    is_bare=True,
                    require_create=True,
                ),
            )
        )

    approval_program = awst_nodes.ContractMethod(
        module_name=contract.module_name,
        class_name=contract.name,
        name="approval_program",
        source_location=router_location,
        args=[],
        return_type=wtypes.bool_wtype,
        body=create_block(
            router_location,
            "abi_bare_routing",
            router,
            reject(contract.source_location),
        ),
        docstring=None,
        abimethod_config=None,
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
        abimethod_config=None,
    )
