import operator
import typing
from collections.abc import Iterable, Mapping, Sequence, Set
from functools import reduce

import attrs
import mypy.nodes
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    BaseClassSubroutineTarget,
    BytesConstant,
    BytesEncoding,
    CompiledContract,
    CreateInnerTransaction,
    Expression,
    IntegerConstant,
    MethodConstant,
    SubmitInnerTransaction,
    TupleExpression,
    UInt64Constant,
)
from puya.awst.txn_fields import TxnField
from puya.awst_build import constants, pytypes
from puya.awst_build.arc4_utils import get_arc4_abimethod_data, get_arc4_baremethod_data
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.arc4._base import ARC4FromLogBuilder
from puya.awst_build.eb.arc4._utils import ARC4Signature, get_arc4_signature
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.compiled import (
    APP_ALLOCATION_FIELDS,
    PROGRAM_FIELDS,
    CompiledContractExpressionBuilder,
)
from puya.awst_build.eb.contracts import ContractTypeExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puya.awst_build.eb.transaction import InnerTransactionExpressionBuilder
from puya.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puya.awst_build.eb.tuple import TupleLiteralBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import (
    get_decorators_by_fullname,
    resolve_member_node,
    symbol_node_is_function,
)
from puya.errors import CodeError
from puya.models import (
    ARC4BareMethodConfig,
    ARC4CreateOption,
    ARC4MethodConfig,
    ContractReference,
    OnCompletionAction,
    TransactionType,
)
from puya.parse import SourceLocation
from puya.utils import StableSet

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
        self,
        context: ASTConversionModuleContext,
        typ: pytypes.PyType,
        source_location: SourceLocation,
        type_info: mypy.nodes.TypeInfo,
    ):
        assert pytypes.ARC4ClientBaseType in typ.bases
        super().__init__(typ, source_location)
        self.context = context
        self.type_info = type_info

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("ARC4Client subclasses cannot be instantiated", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        node = resolve_member_node(self.type_info, name, location)
        if node is None:
            return super().member_access(name, location)
        if symbol_node_is_function(node):
            return ARC4ClientMethodExpressionBuilder(self.context, node, location)
        raise CodeError("static references are only supported for methods", location)


class ARC4ClientMethodExpressionBuilder(FunctionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,  # TODO: yeet me
        node: mypy.nodes.FuncBase | mypy.nodes.Decorator,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self.node = node

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
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
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _abi_call(args, arg_names, location, return_type_annotation=None)


class ABICallTypeBuilder(FunctionBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.PseudoGenericFunctionType)
        self._return_type_annotation = typ.return_type
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
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
        arg_kinds: list[mypy.nodes.ArgKind],
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
            case BaseClassSubroutineInvokerExpressionBuilder(
                target=BaseClassSubroutineTarget(base_class=contract_ref)
            ) as eb:
                method_call = _get_arc4_method_call(eb.context, eb.node, abi_args, location)
            case ContractTypeExpressionBuilder(
                pytype=pytypes.TypeType(typ=typ),
                type_info=type_info,
            ) as eb if pytypes.ARC4ContractBaseType in typ.mro:
                method_call = _get_lifecycle_method_call(
                    eb.context,
                    type_info,
                    abi_args,
                    kind="update" if is_update else "create",
                    location=method_or_type.source_location,
                )
                module_name, class_name = type_info.fullname.rsplit(".", maxsplit=1)
                contract_ref = ContractReference(
                    module_name=module_name,
                    class_name=class_name,
                )
            case _:
                raise CodeError("unexpected argument type", method_or_type.source_location)
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
                compiled, contract_ref, related_location=eb.source_location
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
    return_type_annotation: pytypes.PyType | None,
) -> InstanceBuilder:
    method, abi_args, kwargs = _get_method_abi_args_and_kwargs(
        args, arg_names, _get_python_kwargs(_ABI_CALL_TRANSACTION_FIELDS)
    )
    declared_result_type: pytypes.PyType | None
    arc4_config = None
    match method:
        case None:
            raise CodeError("missing required positional argument 'method'", location)
        case (
            ARC4ClientMethodExpressionBuilder()
            | BaseClassSubroutineInvokerExpressionBuilder() as eb
        ):
            # in this case the arc4 signature and declared return type are inferred
            # TODO: in order to remove the usage of context, we should defer method body evaluation
            #       like we do for function body evaluation, and then these types should make the
            #       resulting metadata (decorator args, function signature) available on them,
            #       instead of shunting the context object around
            method_call = _get_arc4_method_call(eb.context, eb.node, abi_args, location)
            arc4_args = method_call.arc4_args
            arc4_return_type = method_call.arc4_return_type
            arc4_config = method_call.config
            declared_result_type = method_call.method_return_type
            if (
                return_type_annotation is not None
                and return_type_annotation != declared_result_type
            ):
                logger.error(
                    "mismatch between return type of method and generic parameter",
                    location=location,
                )
        case _:
            method_str, signature = get_arc4_signature(method, abi_args, location)
            declared_result_type = return_type_annotation
            if declared_result_type is not None:
                # this will be validated against signature below, by comparing
                # the generated method_selector against the supplied method_str
                signature = attrs.evolve(signature, return_type=declared_result_type)
            elif signature.return_type is None:
                signature = attrs.evolve(signature, return_type=pytypes.NoneType)
            if not signature.method_selector.startswith(method_str):
                logger.error(
                    f"method selector from args '{signature.method_selector}' "
                    f"does not match provided method selector: '{method_str}'",
                    location=method.source_location,
                )
            assert signature.return_type is not None
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
    Return type as declared on the method, this may not be an ARC4 type due to automatic
    type conversion
    """
    arc4_return_type: pytypes.PyType
    """
    ARC4 return type
    """


def _get_arc4_method_call(
    context: ASTConversionModuleContext,
    func_or_dec: mypy.nodes.FuncBase | mypy.nodes.Decorator,
    abi_args: Sequence[NodeBuilder],
    location: SourceLocation,
) -> _ARC4MethodCall:
    if isinstance(func_or_dec, mypy.nodes.Decorator):
        func_def = func_or_dec.func
        decorators = get_decorators_by_fullname(context, func_or_dec)
        abimethod_dec = decorators.get(constants.ABIMETHOD_DECORATOR)
        if abimethod_dec is not None:

            arc4_method_data = get_arc4_abimethod_data(context, abimethod_dec, func_def)
            signature = ARC4Signature(
                arc4_method_data.config.name,
                arc4_method_data.arc4_argument_types,
                arc4_method_data.arc4_return_type,
            )
            return _ARC4MethodCall(
                config=arc4_method_data.config,
                arc4_args=_method_selector_and_arc4_args(signature, abi_args, location),
                method_return_type=arc4_method_data.return_type,
                arc4_return_type=arc4_method_data.arc4_return_type,
            )
        elif baremethod_dec := decorators.get(constants.BAREMETHOD_DECORATOR):
            _expect_bare_method_args(abi_args)
            bare_method_data = get_arc4_baremethod_data(context, baremethod_dec, func_def)
            return _ARC4MethodCall(
                config=bare_method_data,
                arc4_args=[],
                method_return_type=pytypes.NoneType,
                arc4_return_type=pytypes.NoneType,
            )
    raise CodeError("not a valid ARC4 method", location)


def _get_lifecycle_method_call(
    context: ASTConversionModuleContext,
    type_info: mypy.nodes.TypeInfo,
    abi_args: Sequence[NodeBuilder],
    kind: typing.Literal["create", "update"],
    location: SourceLocation,
) -> _ARC4MethodCall:
    # TODO: replace with our own abstraction around classes and their members
    contract = type_info.fullname
    possible_methods = {}
    for base in type_info.mro:
        for symbol_name, symbol in base.names.items():
            if not isinstance(symbol.node, mypy.nodes.Decorator):
                continue
            if symbol_name in possible_methods:  # ignore base methods that are overridden
                continue
            func_def = symbol.node.func
            decorators = get_decorators_by_fullname(context, symbol.node)
            if abimethod_dec := decorators.get(constants.ABIMETHOD_DECORATOR):
                config: ARC4MethodConfig = get_arc4_abimethod_data(
                    context, abimethod_dec, func_def
                ).config
            elif baremethod_dec := decorators.get(constants.BAREMETHOD_DECORATOR):
                config = get_arc4_baremethod_data(context, baremethod_dec, func_def)
            else:
                continue
            if (kind == "create" and config.create != ARC4CreateOption.disallow) or (
                kind == "update"
                and OnCompletionAction.UpdateApplication in config.allowed_completion_types
            ):
                possible_methods[symbol_name] = symbol.node

    try:
        single_method, *others = possible_methods.values()
    except ValueError:
        # can assume a bare create will be created in the absence of any other create methods
        if kind == "create":
            _expect_bare_method_args(abi_args)
            return _ARC4MethodCall(
                config=ARC4BareMethodConfig(source_location=None, create=ARC4CreateOption.require),
                arc4_args=[],
                method_return_type=pytypes.NoneType,
                arc4_return_type=pytypes.NoneType,
            )
        else:
            raise CodeError(f"could not find an update method on {contract}", location) from None
    if others:
        raise CodeError(
            f"found multiple {kind} methods on {contract}, please specify which one to use",
            location,
        )
    return _get_arc4_method_call(context, single_method, abi_args, location)


def _method_selector_and_arc4_args(
    signature: ARC4Signature, abi_args: Sequence[NodeBuilder], location: SourceLocation
) -> Sequence[InstanceBuilder]:
    return [
        BytesExpressionBuilder(
            MethodConstant(value=signature.method_selector, source_location=location)
        ),
        *signature.convert_args(abi_args, location),
    ]


def _create_abi_call_expr(
    *,
    abi_args: Sequence[InstanceBuilder],
    arc4_return_type: pytypes.PyType,
    declared_result_type: pytypes.PyType | None,
    field_nodes: dict[TxnField, NodeBuilder],
    location: SourceLocation,
) -> InstanceBuilder:
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
        match arg_b.pytype:
            case pytypes.TransactionRelatedType():
                logger.error(
                    "transaction arguments are not supported for contract to contract calls",
                    location=arg_b.source_location,
                )
                continue
            case pytypes.AssetType:
                arg_expr = ref_to_arg(TxnField.Assets, arg_b)
            case pytypes.AccountType:
                arg_expr = ref_to_arg(TxnField.Accounts, arg_b)
            case pytypes.ApplicationType:
                arg_expr = ref_to_arg(TxnField.Applications, arg_b)
            case _:
                arg_expr = arg_b.resolve()
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
        wtype=wtypes.WInnerTransactionFields.from_type(txn_type_appl),
        source_location=location,
    )
    itxn_builder = InnerTransactionExpressionBuilder(
        SubmitInnerTransaction(group=create_itxn, source_location=location), itxn_result_pytype
    )

    if declared_result_type is None or declared_result_type == pytypes.NoneType:
        return itxn_builder
    itxn_tmp = itxn_builder.single_eval()
    assert isinstance(itxn_tmp, InnerTransactionExpressionBuilder)
    last_log = itxn_tmp.get_field_value(TxnField.LastLog, pytypes.BytesType, location)
    abi_result = ARC4FromLogBuilder.abi_expr_from_log(arc4_return_type, last_log, location)
    # the declared result wtype may be different to the arc4 signature return wtype
    # due to automatic conversion of ARC4 -> native types
    if declared_result_type != arc4_return_type:
        abi_result = ARC4Decode(
            value=abi_result, wtype=declared_result_type.wtype, source_location=location
        )

    abi_result_builder = builder_for_instance(declared_result_type, abi_result)
    return TupleLiteralBuilder((abi_result_builder, itxn_tmp), location)


def _combine_locs(exprs: Sequence[Expression | NodeBuilder]) -> SourceLocation:
    return reduce(operator.add, (a.source_location for a in exprs))


def _arc4_tuple_from_items(
    items: Sequence[Expression], source_location: SourceLocation
) -> ARC4Encode:
    # TODO: should we just allow TupleExpression to have an ARCTuple wtype?
    args_tuple = TupleExpression.from_items(items, source_location)
    return ARC4Encode(
        value=args_tuple,
        wtype=wtypes.ARC4Tuple(args_tuple.wtype.types, source_location),
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
            "on completion action is not supported by ARC4 method being called",
            location=arg.source_location,
        )
        logger.info("method ARC4 configuration", location=arc4_config.source_location)

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
