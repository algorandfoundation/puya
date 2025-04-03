import typing
from collections.abc import Iterable, Mapping, Sequence, Set

import attrs

from puya import log
from puya.avm import OnCompletionAction, TransactionType
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4CreateOption,
    ARC4Decode,
    ARC4Encode,
    ARC4MethodConfig,
    BytesConstant,
    BytesEncoding,
    CompiledContract,
    CreateInnerTransaction,
    Expression,
    IntegerConstant,
    MethodConstant,
    SubmitInnerTransaction,
    TupleExpression,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation, sequential_source_locations_merge
from puya.program_refs import ContractReference
from puya.utils import StableSet
from puyapy import models
from puyapy.awst_build import constants, pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.arc4._base import ARC4FromLogBuilder
from puyapy.awst_build.eb.arc4._utils import ARC4Signature, get_arc4_signature
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder
from puyapy.awst_build.eb.compiled import (
    APP_ALLOCATION_FIELDS,
    PROGRAM_FIELDS,
    CompiledContractExpressionBuilder,
)
from puyapy.awst_build.eb.contracts import ContractTypeExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puyapy.awst_build.eb.transaction import InnerTransactionExpressionBuilder
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.tuple import TupleExpressionBuilder, TupleLiteralBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puyapy.models import (
    ARC4ABIMethodData,
    ARC4BareMethodData,
    ARC4MethodData,
    ContractFragmentBase,
    ContractFragmentMethod,
)

logger = log.get_logger(__name__)

_FIELD_TO_ITXN_ARGUMENT = {arg.field: arg for arg in PYTHON_ITXN_ARGUMENTS.values()}
_ABI_CALL_TRANSACTION_FIELDS = [
    TxnField.ApplicationID,
    TxnField.OnCompletion,
    TxnField.ApprovalProgramPages,
    TxnField.ClearStateProgramPages,
    TxnField.GlobalNumUint,
    TxnField.GlobalNumByteSlice,
    TxnField.LocalNumUint,
    TxnField.LocalNumByteSlice,
    TxnField.ExtraProgramPages,
    TxnField.Fee,
    TxnField.Sender,
    TxnField.Note,
    TxnField.RekeyTo,
]
_ARC4_CREATE_TRANSACTION_FIELDS = [
    TxnField.OnCompletion,
    TxnField.Fee,
    TxnField.Sender,
    TxnField.Note,
    TxnField.RekeyTo,
]
_ARC4_UPDATE_TRANSACTION_FIELDS = [
    TxnField.ApplicationID,
    TxnField.Fee,
    TxnField.Sender,
    TxnField.Note,
    TxnField.RekeyTo,
]
_COMPILED_KWARG = "compiled"


class ARC4ClientTypeBuilder(TypeBuilder):
    def __init__(
        self, typ: pytypes.PyType, source_location: SourceLocation, fragment: ContractFragmentBase
    ):
        assert pytypes.ARC4ClientBaseType in typ.bases
        super().__init__(typ, source_location)
        self.fragment: typing.Final = fragment

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("ARC4Client subclasses cannot be instantiated", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        method = self.fragment.resolve_method(name)
        if method is None:
            return super().member_access(name, location)
        return ARC4ClientMethodExpressionBuilder(method, location)


class ARC4ClientMethodExpressionBuilder(FunctionBuilder):
    def __init__(
        self,
        method: ContractFragmentMethod,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.method: typing.Final = method

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError(
            f"can't invoke client methods directly, use {constants.CLS_ARC4_ABI_CALL}", location
        )


class ABICallGenericTypeBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _abi_call(args, arg_names, location, return_type_annotation=pytypes.NoneType)


class ABICallTypeBuilder(FunctionBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.PseudoGenericFunctionType)
        self._return_type_annotation = typ.return_type
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _abi_call(
            args, arg_names, location, return_type_annotation=self._return_type_annotation
        )


def _get_python_kwargs(fields: Sequence[TxnField]) -> Set[str]:
    return StableSet.from_iter(
        arg for arg, param in PYTHON_ITXN_ARGUMENTS.items() if param.field in fields
    )


class _ARC4CompilationFunctionBuilder(FunctionBuilder):
    allowed_fields: Sequence[TxnField]

    @property
    def allowed_kwargs(self) -> Set[str]:
        return {_COMPILED_KWARG, *_get_python_kwargs(self.allowed_fields)}

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        # if on_completion not allowed, it must be an update
        is_update = TxnField.OnCompletion not in self.allowed_fields
        method_or_type, abi_args, kwargs = _get_method_abi_args_and_kwargs(
            args, arg_names, self.allowed_kwargs
        )
        compiled = None
        if compiled_node := kwargs.pop(_COMPILED_KWARG, None):
            compiled = expect.argument_of_type_else_dummy(
                compiled_node, pytypes.CompiledContractType
            )

        match method_or_type:
            case None:
                raise CodeError("missing required positional argument 'method'", location)
            case BaseClassSubroutineInvokerExpressionBuilder(method=fmethod, cref=contract_ref):
                method_call = _get_arc4_method_call(fmethod, abi_args, location)
            case ContractTypeExpressionBuilder(
                fragment=fragment, pytype=pytypes.TypeType(typ=typ)
            ) if pytypes.ARC4ContractBaseType < typ:
                contract_ref = fragment.id
                method_call = _get_lifecycle_method_call(
                    fragment,
                    abi_args,
                    kind="update" if is_update else "create",
                    location=method_or_type.source_location,
                )
            case other:
                expect.not_this_type(other, default=expect.default_raise)
        if compiled is None:
            compiled = CompiledContractExpressionBuilder(
                CompiledContract(
                    contract=contract_ref,
                    wtype=pytypes.CompiledContractType.wtype,
                    source_location=location,
                )
            )
        else:
            _warn_if_different_contract(
                compiled, contract_ref, related_location=method_or_type.source_location
            )
        field_nodes = {PYTHON_ITXN_ARGUMENTS[kwarg].field: node for kwarg, node in kwargs.items()}
        if is_update:
            _add_on_completion(field_nodes, OnCompletionAction.UpdateApplication, location)
        # if on_completion is not set but can be inferred from config then use that
        elif (
            TxnField.OnCompletion not in field_nodes
            and (on_completion := _get_singular_on_complete(method_call.config)) is not None
        ):
            _add_on_completion(field_nodes, on_completion, location)

        compiled = compiled.single_eval()
        for member_name, field in PROGRAM_FIELDS.items():
            field_nodes[field] = compiled.member_access(member_name, location)
        # is creating
        if not is_update:
            # add all app allocation fields
            for member_name, field in APP_ALLOCATION_FIELDS.items():
                field_nodes[field] = compiled.member_access(member_name, location)
        _validate_transaction_kwargs(
            field_nodes,
            method_call.config,
            method_location=method_or_type.source_location,
            call_location=location,
        )
        return _create_abi_call_expr(
            abi_args=method_call.arc4_args,
            arc4_return_type=method_call.arc4_return_type,
            declared_result_type=method_call.method_return_type,
            field_nodes=field_nodes,
            location=location,
        )


def _warn_if_different_contract(
    compiled: InstanceBuilder, contract: ContractReference, *, related_location: SourceLocation
) -> None:
    # naive check for mismatch between method and compiled parameters
    expr = compiled.resolve()
    if isinstance(expr, CompiledContract) and expr.contract != contract:
        logger.warning(
            "compiled parameter is for a different contract",
            location=compiled.source_location,
        )
        logger.info("other contract reference", location=related_location)


class ARC4CreateFunctionBuilder(_ARC4CompilationFunctionBuilder):
    allowed_fields: Sequence[TxnField] = _ARC4_CREATE_TRANSACTION_FIELDS


class ARC4UpdateFunctionBuilder(_ARC4CompilationFunctionBuilder):
    allowed_fields: Sequence[TxnField] = _ARC4_UPDATE_TRANSACTION_FIELDS


def _abi_call(
    args: Sequence[NodeBuilder],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    return_type_annotation: pytypes.PyType,
) -> InstanceBuilder:
    method, abi_args, kwargs = _get_method_abi_args_and_kwargs(
        args, arg_names, _get_python_kwargs(_ABI_CALL_TRANSACTION_FIELDS)
    )
    declared_result_type: pytypes.PyType
    arc4_config = None
    match method:
        case None:
            raise CodeError("missing required positional argument 'method'", location)
        case (
            ARC4ClientMethodExpressionBuilder(method=fmethod)
            | BaseClassSubroutineInvokerExpressionBuilder(method=fmethod)
        ):
            # in this case the arc4 signature and declared return type are inferred
            method_call = _get_arc4_method_call(fmethod, abi_args, location)
            arc4_args = method_call.arc4_args
            arc4_return_type = method_call.arc4_return_type
            arc4_config = method_call.config
            declared_result_type = method_call.method_return_type
            if return_type_annotation not in (declared_result_type, pytypes.NoneType):
                logger.error(
                    "mismatch between return type of method and generic parameter",
                    location=location,
                )
        case _:
            method_str, signature = get_arc4_signature(method, abi_args, location)
            declared_result_type = return_type_annotation
            if declared_result_type != pytypes.NoneType:
                # this will be validated against signature below, by comparing
                # the generated method_selector against the supplied method_str
                signature = attrs.evolve(signature, return_type=declared_result_type)
            if not signature.method_selector.startswith(method_str):
                logger.error(
                    f"method selector from args '{signature.method_selector}' "
                    f"does not match provided method selector: '{method_str}'",
                    location=method.source_location,
                )
            arc4_args = _method_selector_and_arc4_args(signature, abi_args, location)
            arc4_return_type = signature.return_type

    field_nodes = {PYTHON_ITXN_ARGUMENTS[kwarg].field: node for kwarg, node in kwargs.items()}
    # set on_completion if it can be inferred from config
    if (
        TxnField.OnCompletion not in field_nodes
        and (on_completion := _get_singular_on_complete(arc4_config)) is not None
    ):
        _add_on_completion(field_nodes, on_completion, location)

    _validate_transaction_kwargs(
        field_nodes,
        arc4_config,
        method_location=method.source_location,
        call_location=location,
    )
    return _create_abi_call_expr(
        arc4_return_type=arc4_return_type,
        abi_args=arc4_args,
        declared_result_type=declared_result_type,
        field_nodes=field_nodes,
        location=location,
    )


def _get_method_abi_args_and_kwargs(
    args: Sequence[NodeBuilder], arg_names: list[str | None], allowed_kwargs: Set[str]
) -> tuple[NodeBuilder | None, Sequence[NodeBuilder], dict[str, NodeBuilder]]:
    method: NodeBuilder | None = None
    abi_args = list[NodeBuilder]()
    kwargs = dict[str, NodeBuilder]()
    for idx, (arg_name, arg) in enumerate(zip(arg_names, args, strict=True)):
        if arg_name is None:
            if idx == 0:
                method = arg
            else:
                abi_args.append(arg)
        elif arg_name in allowed_kwargs:
            kwargs[arg_name] = arg
        else:
            logger.error("unrecognised keyword argument", location=arg.source_location)
    return method, abi_args, kwargs


@attrs.frozen
class _ARC4MethodCall:
    config: ARC4MethodConfig | None
    arc4_args: Sequence[InstanceBuilder]
    method_return_type: pytypes.PyType
    """
    Return type as declared on the method, this may not be an ARC-4 type due to automatic
    type conversion
    """
    arc4_return_type: pytypes.PyType
    """
    ARC-4 return type
    """


def _get_arc4_method_call(
    data: ContractFragmentMethod, abi_args: Sequence[NodeBuilder], location: SourceLocation
) -> _ARC4MethodCall:
    if data.metadata is None:
        raise CodeError("not a valid ARC-4 method", location)
    return _map_arc4_method_data_to_call(data.metadata, abi_args, location)


def _map_arc4_method_data_to_call(
    data: ARC4MethodData,
    abi_args: Sequence[NodeBuilder],
    location: SourceLocation,
) -> _ARC4MethodCall:
    match data:
        case ARC4ABIMethodData() as abi_method_data:
            signature = ARC4Signature(
                method_name=abi_method_data.config.name,
                arg_types=abi_method_data.arc4_argument_types,
                return_type=abi_method_data.arc4_return_type,
                source_location=location,
            )
            return _ARC4MethodCall(
                config=abi_method_data.config,
                arc4_args=_method_selector_and_arc4_args(signature, abi_args, location),
                method_return_type=abi_method_data.return_type,
                arc4_return_type=abi_method_data.arc4_return_type,
            )
        case ARC4BareMethodData() as bare_method_data:
            _expect_bare_method_args(abi_args)
            return _ARC4MethodCall(
                config=bare_method_data.config,
                arc4_args=[],
                method_return_type=pytypes.NoneType,
                arc4_return_type=pytypes.NoneType,
            )
        case other:
            typing.assert_never(other)


def _get_lifecycle_method_call(
    fragment: ContractFragmentBase,
    abi_args: Sequence[NodeBuilder],
    kind: typing.Literal["create", "update"],
    location: SourceLocation,
) -> _ARC4MethodCall:
    if kind == "create":
        possible_methods = list(fragment.find_arc4_method_metadata(can_create=True))
    elif kind == "update":
        possible_methods = list(
            fragment.find_arc4_method_metadata(oca=OnCompletionAction.UpdateApplication)
        )

    try:
        single_method, *others = possible_methods
    except ValueError:
        raise CodeError(f"could not find {kind} method on {fragment.id}", location) from None
    if others:
        raise CodeError(
            f"found multiple {kind} methods on {fragment.id}, please specify which one to use",
            location,
        )
    method_call = _map_arc4_method_data_to_call(single_method, abi_args, location)
    # remove method_return_type from result
    # so _create_abi_call_expr does not attempt to include any decoded ARC-4 result
    # as per the stubs overload for arc4_create/arc4_update with a Contract type
    return attrs.evolve(method_call, method_return_type=pytypes.NoneType)


def _method_selector_and_arc4_args(
    signature: ARC4Signature, abi_args: Sequence[NodeBuilder], location: SourceLocation
) -> Sequence[InstanceBuilder]:
    return [
        BytesExpressionBuilder(
            MethodConstant(value=signature.method_selector, source_location=location)
        ),
        *signature.convert_args(abi_args, expect_itxn_args=True),
    ]


def _create_abi_call_expr(
    *,
    abi_args: Sequence[InstanceBuilder],
    arc4_return_type: pytypes.PyType,
    declared_result_type: pytypes.PyType,
    field_nodes: dict[TxnField, NodeBuilder],
    location: SourceLocation,
) -> InstanceBuilder:
    group = []
    array_fields: dict[TxnField, list[Expression]] = {
        TxnField.ApplicationArgs: [],
        TxnField.Accounts: [],
        TxnField.Applications: [],
        TxnField.Assets: [],
    }

    def ref_to_arg(ref_field: TxnField, arg: InstanceBuilder) -> Expression:
        # TODO: what about references that are used more than once?
        implicit_offset = 1 if ref_field in (TxnField.Accounts, TxnField.Applications) else 0
        ref_list = array_fields[ref_field]
        ref_index = len(ref_list)
        ref_list.append(arg.resolve())
        return BytesConstant(
            value=(ref_index + implicit_offset).to_bytes(length=1),
            encoding=BytesEncoding.base16,
            source_location=arg.source_location,
        )

    for arg_b in abi_args:
        arg_expr = None
        match arg_b.pytype:
            case pytypes.InnerTransactionFieldsetType():
                group.append(arg_b.resolve())
                # no arg_expr as txn aren't part of the app args
            case pytypes.TransactionRelatedType():
                logger.error(
                    "only inner transaction types can be used to call another contract",
                    location=arg_b.source_location,
                )
            case pytypes.AssetType:
                arg_expr = ref_to_arg(TxnField.Assets, arg_b)
            case pytypes.AccountType:
                arg_expr = ref_to_arg(TxnField.Accounts, arg_b)
            case pytypes.ApplicationType:
                arg_expr = ref_to_arg(TxnField.Applications, arg_b)
            case _:
                arg_expr = arg_b.resolve()
        if arg_expr is not None:
            array_fields[TxnField.ApplicationArgs].append(arg_expr)

    txn_type_appl = TransactionType.appl
    fields: dict[TxnField, Expression] = {
        TxnField.Fee: UInt64Constant(value=0, source_location=location),
        TxnField.TypeEnum: UInt64Constant(
            value=txn_type_appl.value, teal_alias=txn_type_appl.name, source_location=location
        ),
    }
    for arr_field, arr_field_values in array_fields.items():
        if arr_field_values:
            if arr_field == TxnField.ApplicationArgs and len(arr_field_values) > 16:
                args_to_pack = arr_field_values[15:]
                arr_field_values[15:] = [
                    _arc4_tuple_from_items(args_to_pack, _combine_locs(args_to_pack))
                ]
            fields[arr_field] = TupleExpression.from_items(
                arr_field_values, _combine_locs(arr_field_values)
            )

    for field, field_node in field_nodes.items():
        params = _FIELD_TO_ITXN_ARGUMENT[field]
        if params is None:
            logger.error("unrecognised keyword argument", location=field_node.source_location)
        else:
            fields[field] = params.validate_and_convert(field_node).resolve()

    itxn_result_pytype = pytypes.InnerTransactionResultTypes[txn_type_appl]
    create_itxn = CreateInnerTransaction(
        fields=fields,
        wtype=pytypes.InnerTransactionFieldsetTypes[txn_type_appl].wtype,
        source_location=location,
    )
    group.append(create_itxn)
    if len(group) == 1:
        itxn_builder: InstanceBuilder = InnerTransactionExpressionBuilder(
            SubmitInnerTransaction(itxns=group, source_location=location), itxn_result_pytype
        )
    else:
        itxn_types = []
        for itxn in group:
            assert isinstance(itxn.wtype, wtypes.WInnerTransactionFields)
            itxn_types.append(pytypes.InnerTransactionResultTypes[itxn.wtype.transaction_type])
        itxn_tuple_result_pytype = pytypes.GenericTupleType.parameterise(
            itxn_types,
            location,
        )
        itxn_tuple_builder = TupleExpressionBuilder(
            SubmitInnerTransaction(itxns=group, source_location=location),
            itxn_tuple_result_pytype,
        ).single_eval()
        itxn_builder = InnerTransactionExpressionBuilder(
            TupleItemExpression(
                base=itxn_tuple_builder.resolve(),
                index=-1,
                source_location=location,
            ),
            itxn_result_pytype,
        )

    if declared_result_type == pytypes.NoneType:
        return itxn_builder
    itxn_builder = itxn_builder.single_eval()
    assert isinstance(itxn_builder, InnerTransactionExpressionBuilder)
    last_log = itxn_builder.get_field_value(TxnField.LastLog, pytypes.BytesType, location)
    abi_result = ARC4FromLogBuilder.abi_expr_from_log(arc4_return_type, last_log, location)
    # the declared result type may be different to the arc4 signature return type
    # due to automatic conversion of ARC-4 -> native types
    if declared_result_type != arc4_return_type:
        abi_result = ARC4Decode(
            value=abi_result,
            wtype=declared_result_type.checked_wtype(location),
            source_location=location,
        )

    abi_result_builder = builder_for_instance(declared_result_type, abi_result)
    return TupleLiteralBuilder((abi_result_builder, itxn_builder), location)


def _combine_locs(exprs: Sequence[Expression | NodeBuilder]) -> SourceLocation:
    return sequential_source_locations_merge(a.source_location for a in exprs)


def _arc4_tuple_from_items(
    items: Sequence[Expression], source_location: SourceLocation
) -> ARC4Encode:
    # TODO: should we just allow TupleExpression to have an ARCTuple wtype?
    args_tuple = TupleExpression.from_items(items, source_location)
    return ARC4Encode(
        value=args_tuple,
        wtype=wtypes.ARC4Tuple(types=args_tuple.wtype.types, source_location=source_location),
        source_location=source_location,
    )


def _expect_bare_method_args(abi_args: Sequence[NodeBuilder]) -> None:
    if abi_args:
        logger.error("unexpected args for bare method", location=_combine_locs(abi_args))


def _validate_transaction_kwargs(
    field_nodes: Mapping[TxnField, NodeBuilder],
    arc4_config: ARC4MethodConfig | None,
    *,
    method_location: SourceLocation,
    call_location: SourceLocation,
) -> None:
    # note these values may be None which indicates their value is unknown at compile time
    on_completion = _get_on_completion(field_nodes)
    is_update = on_completion == OnCompletionAction.UpdateApplication
    is_create = _is_creating(field_nodes)

    if is_create:
        # app_id not provided but method doesn't support creating
        if arc4_config and arc4_config.create == ARC4CreateOption.disallow:
            logger.error("method cannot be used to create application", location=method_location)
        # required args for creation missing
        else:
            _check_program_fields_are_present(
                "missing required arguments to create app", field_nodes, call_location
            )
    if is_update:
        if arc4_config and (
            OnCompletionAction.UpdateApplication not in arc4_config.allowed_completion_types
        ):
            logger.error("method cannot be used to update application", location=method_location)
        else:
            _check_program_fields_are_present(
                "missing required arguments to update app", field_nodes, call_location
            )
    # on_completion not valid for arc4_config
    elif (
        on_completion is not None
        and arc4_config
        and on_completion not in arc4_config.allowed_completion_types
    ):
        arg = field_nodes[TxnField.OnCompletion]
        logger.error(
            "on completion action is not supported by ARC-4 method being called",
            location=arg.source_location,
        )
        logger.info("method ARC-4 configuration", location=arc4_config.source_location)

    # programs provided when known not to be creating or updating
    if is_create is False and is_update is False:
        _check_fields_not_present(
            "provided argument is only valid when creating or updating an application",
            PROGRAM_FIELDS.values(),
            field_nodes,
        )
    if is_create is False:
        _check_fields_not_present(
            "provided argument is only valid when creating an application",
            APP_ALLOCATION_FIELDS.values(),
            field_nodes,
        )


def _check_program_fields_are_present(
    error_message: str, field_nodes: Mapping[TxnField, NodeBuilder], location: SourceLocation
) -> None:
    if missing_fields := [field for field in PROGRAM_FIELDS.values() if field not in field_nodes]:
        logger.error(
            f"{error_message}: {', '.join(_get_python_kwargs(missing_fields))}",
            location=location,
        )


def _check_fields_not_present(
    error_message: str,
    fields_to_omit: Iterable[TxnField],
    field_nodes: Mapping[TxnField, NodeBuilder],
) -> None:
    for field in fields_to_omit:
        if node := field_nodes.get(field):
            logger.error(error_message, location=node.source_location)


def _get_singular_on_complete(config: ARC4MethodConfig | None) -> OnCompletionAction | None:
    if config:
        try:
            (on_complete,) = config.allowed_completion_types
        except ValueError:
            pass
        else:
            return on_complete
    return None


def _get_on_completion(field_nodes: Mapping[TxnField, NodeBuilder]) -> OnCompletionAction | None:
    """
    Returns OnCompletionAction if it is statically known, otherwise returns None
    """
    match field_nodes.get(TxnField.OnCompletion):
        case None:
            return OnCompletionAction.NoOp
        case InstanceBuilder(pytype=pytypes.OnCompleteActionType) as eb:
            value = eb.resolve()
            if isinstance(value, IntegerConstant):
                return OnCompletionAction(value.value)
    return None


def _is_creating(field_nodes: Mapping[TxnField, NodeBuilder]) -> bool | None:
    """
    Returns app_id == 0 if app_id is statically known, otherwise returns None
    """
    match field_nodes.get(TxnField.ApplicationID):
        case None:
            return True
        case LiteralBuilder(value=int(app_id)):
            return app_id == 0
    return None


def _add_on_completion(
    field_nodes: dict[TxnField, NodeBuilder],
    on_complete: OnCompletionAction,
    location: SourceLocation,
) -> None:
    # if NoOp can just omit
    if on_complete == OnCompletionAction.NoOp:
        return
    field_nodes[TxnField.OnCompletion] = UInt64ExpressionBuilder(
        UInt64Constant(
            source_location=location, value=on_complete.value, teal_alias=on_complete.name
        ),
        enum_type=pytypes.OnCompleteActionType,
    )
