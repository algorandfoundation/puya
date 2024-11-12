import typing
from collections.abc import Iterable, Mapping, Sequence

from immutabledict import immutabledict

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


def _assert(
    *, condition: awst_nodes.Expression, comment: str | None, source_location: SourceLocation
) -> awst_nodes.IntrinsicCall:
    return awst_nodes.IntrinsicCall(
        wtype=wtypes.void_wtype,
        stack_args=[condition],
        op_code="assert",
        source_location=source_location,
        comment=comment,
    )


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
    location: SourceLocation, method: awst_nodes.ContractMethod, *args: awst_nodes.Expression
) -> awst_nodes.SubroutineCallExpression:
    return awst_nodes.SubroutineCallExpression(
        target=awst_nodes.ContractMethodTarget(cref=method.cref, member_name=method.member_name),
        args=[awst_nodes.CallArg(name=None, value=arg) for arg in args],
        wtype=method.return_type,
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
    log_op = awst_nodes.IntrinsicCall(
        op_code="log",
        stack_args=[abi_log],
        wtype=wtypes.void_wtype,
        source_location=location,
    )
    return awst_nodes.ExpressionStatement(log_op)


def assert_create_state(
    config: ARC4MethodConfig, location: SourceLocation
) -> Sequence[awst_nodes.Statement]:
    app_id = _txn("ApplicationID", wtypes.uint64_wtype, location)
    match config.create:
        case ARC4CreateOption.allow:
            # if create is allowed but not required, we don't need to check anything
            return ()
        case ARC4CreateOption.disallow:
            condition = _non_zero(app_id)
            comment = "can only call when not creating"
        case ARC4CreateOption.require:
            condition = _is_zero(app_id)
            comment = "can only call when creating"
        case invalid:
            typing.assert_never(invalid)
    return [
        awst_nodes.ExpressionStatement(
            expr=_assert(condition=condition, comment=comment, source_location=location)
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
            expr=_assert(
                condition=condition,
                comment=f"OnCompletion is not {oca_desc}",
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
            else:
                converted = maybe_avm_to_arc4_equivalent_type(a)
                if converted is not None:
                    arc4_type = converted
                elif _reference_type_array(a) is not None:
                    arc4_type = wtypes.arc4_byte_alias
                else:
                    raise CodeError(f"not an ARC4 type or native equivalent: {a}", location)
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
                if abi_arg.wtype != arg:
                    abi_arg = awst_nodes.ARC4Decode(
                        value=abi_arg, wtype=arg, source_location=location
                    )
                yield abi_arg


def route_abi_methods(
    location: SourceLocation,
    methods: dict[awst_nodes.ContractMethod, ARC4ABIMethodConfig],
) -> awst_nodes.Block:
    method_routing_cases = dict[awst_nodes.Expression, awst_nodes.Block]()
    seen_signatures = set[str]()
    for method, config in methods.items():
        abi_loc = config.source_location or location
        abi_args = list(_map_abi_args([a.wtype for a in method.args], location))
        method_result = call(abi_loc, method, *abi_args)
        match method.return_type:
            case wtypes.void_wtype:
                call_and_maybe_log = awst_nodes.ExpressionStatement(method_result)
            case wtypes.ARC4Type():
                call_and_maybe_log = log_arc4_result(abi_loc, method_result)
            case _:
                converted_return_type = maybe_avm_to_arc4_equivalent_type(method.return_type)
                if converted_return_type is None:
                    raise CodeError(
                        f"{method.return_type} is not a valid ABI return type",
                        method.source_location,
                    )
                arc4_encoded = awst_nodes.ARC4Encode(
                    value=method_result,
                    wtype=converted_return_type,
                    source_location=method_result.source_location,
                )
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
) -> dict[awst_nodes.ContractMethod, ARC4Method]:
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

    arc4_method_metadata = dict[awst_nodes.ContractMethod, ARC4Method]()
    for m, bare_method_config in bare_methods.items():
        arc4_method_metadata[m] = ARC4BareMethod(
            desc=m.documentation.description,
            config=bare_method_config,
        )
    for m, abi_method_config in abi_methods.items():
        arc4_method_metadata[m] = ARC4ABIMethod(
            name=m.member_name,
            desc=m.documentation.description,
            args=[
                ARC4MethodArg(
                    name=a.name,
                    type_=_wtype_to_arc4(a.wtype),
                    struct=_get_arc4_struct_name(a.wtype),
                    desc=m.documentation.args.get(a.name),
                )
                for a in m.args
            ],
            returns=ARC4Returns(
                desc=m.documentation.returns,
                type_=_wtype_to_arc4(m.return_type),
                struct=_get_arc4_struct_name(m.return_type),
            ),
            events=[],
            config=abi_method_config,
        )

    return arc4_method_metadata


def _get_arc4_struct_name(wtype: wtypes.WType) -> str | None:
    return (
        wtype.name
        if isinstance(wtype, wtypes.ARC4Struct | wtypes.WTuple) and wtype.fields
        else None
    )


def create_abi_router(
    contract: awst_nodes.Contract,
    arc4_methods_with_configs: dict[awst_nodes.ContractMethod, ARC4Method],
) -> awst_nodes.ContractMethod:
    router_location = contract.source_location
    abi_methods = {}
    bare_methods = {}
    for m, arc4_method in arc4_methods_with_configs.items():
        arc4_config = arc4_method.config
        assert arc4_config is m.arc4_method_config
        if isinstance(arc4_config, ARC4BareMethodConfig):
            bare_methods[m] = arc4_config
        elif isinstance(arc4_config, ARC4ABIMethodConfig):
            abi_methods[m] = arc4_config
        else:
            typing.assert_never(arc4_config)

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
    )
    return approval_program


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
        ):
            return wtype.name
        case wtypes.WGroupTransaction(transaction_type=transaction_type):
            return transaction_type.name if transaction_type else "txn"
    converted = maybe_avm_to_arc4_equivalent_type(wtype)
    if converted is None:
        raise CodeError(f"not an ARC4 type or native equivalent: {wtype}", loc)
    return _wtype_to_arc4(converted, loc)


def _reference_type_array(wtype: wtypes.WType) -> str | None:
    match wtype:
        case wtypes.asset_wtype:
            return "Assets"
        case wtypes.account_wtype:
            return "Accounts"
        case wtypes.application_wtype:
            return "Applications"
    return None


def maybe_avm_to_arc4_equivalent_type(wtype: wtypes.WType) -> wtypes.ARC4Type | None:
    match wtype:
        case wtypes.bool_wtype:
            return wtypes.arc4_bool_wtype
        case wtypes.uint64_wtype:
            return wtypes.ARC4UIntN(n=64, source_location=None)
        case wtypes.biguint_wtype:
            return wtypes.ARC4UIntN(n=512, source_location=None)
        case wtypes.bytes_wtype:
            return wtypes.ARC4DynamicArray(
                element_type=wtypes.arc4_byte_alias, native_type=wtype, source_location=None
            )
        case wtypes.string_wtype:
            return wtypes.arc4_string_alias
        case wtypes.WTuple(types=tuple_item_types) as wtuple:
            arc4_item_types = []
            for t in tuple_item_types:
                if isinstance(t, wtypes.ARC4Type):
                    arc4_item_types.append(t)
                else:
                    converted = maybe_avm_to_arc4_equivalent_type(t)
                    if converted is None:
                        return None
                    arc4_item_types.append(converted)
            if wtuple.fields:
                return wtypes.ARC4Struct(
                    name=wtuple.name,
                    desc=wtuple.desc,
                    frozen=True,
                    fields=immutabledict(zip(wtuple.fields, arc4_item_types, strict=True)),
                )
            else:
                return wtypes.ARC4Tuple(types=arc4_item_types, source_location=None)
        case _:
            return None
