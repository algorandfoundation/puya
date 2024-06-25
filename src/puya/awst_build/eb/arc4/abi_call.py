import operator
import typing
from collections.abc import Sequence
from functools import reduce

import attrs
import mypy.nodes
import mypy.types

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import (
    TXN_FIELDS_BY_IMMEDIATE,
    ARC4Decode,
    BytesConstant,
    BytesEncoding,
    CreateInnerTransaction,
    Expression,
    MethodConstant,
    SubmitInnerTransaction,
    TupleExpression,
    TxnField,
    TxnFields,
    UInt64Constant,
)
from puya.awst_build import constants, pytypes
from puya.awst_build.arc4_utils import get_arc4_abimethod_data
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.arc4._base import ARC4FromLogBuilder
from puya.awst_build.eb.arc4._utils import ARC4Signature, get_arc4_signature
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puya.awst_build.eb.transaction import InnerTransactionExpressionBuilder
from puya.awst_build.eb.transaction.fields import get_field_python_name
from puya.awst_build.eb.transaction.inner_params import get_field_expr
from puya.awst_build.eb.tuple import TupleLiteralBuilder
from puya.awst_build.utils import (
    get_decorators_by_fullname,
    require_instance_builder,
    resolve_method_from_type_info,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)

_APP_TRANSACTION_FIELDS = {
    get_field_python_name(field): field
    for field in (
        TXN_FIELDS_BY_IMMEDIATE[immediate]
        for immediate in (
            "ApplicationID",
            "OnCompletion",
            "ApprovalProgram",
            "ClearStateProgram",
            "GlobalNumUint",
            "GlobalNumByteSlice",
            "LocalNumUint",
            "LocalNumByteSlice",
            "ExtraProgramPages",
            "Fee",
            "Sender",
            "Note",
            "RekeyTo",
        )
    )
}


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
    def member_access(
        self, name: str, expr: mypy.nodes.Expression, location: SourceLocation
    ) -> NodeBuilder:
        func_or_dec = resolve_method_from_type_info(self.type_info, name, location)
        if func_or_dec is None:
            raise CodeError(f"unknown member {name!r} of {self.type_info.fullname!r}", location)
        return ARC4ClientMethodExpressionBuilder(self.context, func_or_dec, location)


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


def _abi_call(
    args: Sequence[NodeBuilder],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    return_type_annotation: pytypes.PyType | None,
) -> InstanceBuilder:
    method: NodeBuilder | None = None
    abi_args = list[InstanceBuilder]()
    transaction_kwargs = dict[str, InstanceBuilder]()
    for idx, (arg_name, arg) in enumerate(zip(arg_names, args, strict=True)):
        if arg_name is None:
            if idx == 0:
                method = arg
            else:
                abi_args.append(require_instance_builder(arg))
        else:
            transaction_kwargs[arg_name] = require_instance_builder(arg)

    declared_result_type: pytypes.PyType | None
    match method:
        case None:
            raise CodeError("missing required positional argument 'method'", location)
        case ARC4ClientMethodExpressionBuilder(
            context=context, node=node
        ) | BaseClassSubroutineInvokerExpressionBuilder(context=context, node=node):
            # in this case the arc4 signature and declared return type are inferred
            # TODO: in order to remove the usage of context, we should defer method body evaluation
            #       like we do for function body evaluation, and then these types should make the
            #       resulting metadata (decorator args, function signature) available on them,
            #       instead of shunting the context object around
            signature, declared_result_type = _get_arc4_signature_and_return_pytype(
                context, node, location
            )
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

    if signature.return_type is None:
        raise InternalError("expected ARC4Signature.return_type to be defined", location)

    arc4_args = signature.convert_args(abi_args, location)

    return _create_abi_call_expr(
        method_selector=signature.method_selector,
        signature_return_type=signature.return_type,
        abi_args=arc4_args,
        declared_result_type=declared_result_type,
        transaction_kwargs=transaction_kwargs,
        location=location,
    )


def _get_arc4_signature_and_return_pytype(
    context: ASTConversionModuleContext,
    func_or_dec: mypy.nodes.FuncBase | mypy.nodes.Decorator,
    location: SourceLocation,
) -> tuple[ARC4Signature, pytypes.PyType]:
    if isinstance(func_or_dec, mypy.nodes.Decorator):
        decorators = get_decorators_by_fullname(context, func_or_dec)
        abimethod_dec = decorators.get(constants.ABIMETHOD_DECORATOR)
        if abimethod_dec is not None:
            func_def = func_or_dec.func
            arc4_method_data = get_arc4_abimethod_data(context, abimethod_dec, func_def)
            arc4_return_type = arc4_method_data.arc4_return_type
            arc4_arg_types = arc4_method_data.arc4_argument_types
            name = arc4_method_data.config.name
            return (
                ARC4Signature(name, arc4_arg_types, arc4_return_type),
                arc4_method_data.return_type,
            )
    raise CodeError("not a valid ARC4 method", location)


def _create_abi_call_expr(
    *,
    method_selector: str,
    signature_return_type: pytypes.PyType,
    abi_args: Sequence[InstanceBuilder],
    declared_result_type: pytypes.PyType | None,
    transaction_kwargs: dict[str, InstanceBuilder],
    location: SourceLocation,
) -> InstanceBuilder:

    array_fields: dict[TxnField, list[Expression]] = {
        TxnFields.app_args: [MethodConstant(value=method_selector, source_location=location)],
        TxnFields.accounts: [],
        TxnFields.apps: [],
        TxnFields.assets: [],
    }

    def ref_to_arg(ref_field: TxnField, arg: InstanceBuilder) -> Expression:
        # TODO: what about references that are used more than once?
        implicit_offset = 1 if ref_field in (TxnFields.accounts, TxnFields.apps) else 0
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
                arg_expr = ref_to_arg(TxnFields.assets, arg_b)
            case pytypes.AccountType:
                arg_expr = ref_to_arg(TxnFields.accounts, arg_b)
            case pytypes.ApplicationType:
                arg_expr = ref_to_arg(TxnFields.apps, arg_b)
            case _:
                arg_expr = arg_b.resolve()
        array_fields[TxnFields.app_args].append(arg_expr)

    txn_type_appl = constants.TransactionType.appl
    fields: dict[TxnField, Expression] = {
        TxnFields.fee: UInt64Constant(value=0, source_location=location),
        TxnFields.type: UInt64Constant(
            value=txn_type_appl.value, teal_alias=txn_type_appl.name, source_location=location
        ),
    }
    for arr_field, arr_field_values in array_fields.items():
        if arr_field_values:
            if arr_field == TxnFields.app_args and len(arr_field_values) > 16:
                args_to_pack = arr_field_values[15:]
                arr_field_values[15:] = [
                    _arc4_tuple_from_items(args_to_pack, _combine_locs(args_to_pack))
                ]
            fields[arr_field] = TupleExpression.from_items(
                arr_field_values, _combine_locs(arr_field_values)
            )
    for field_python_name, field in _APP_TRANSACTION_FIELDS.items():
        if value := transaction_kwargs.pop(field_python_name, None):
            field, field_expr = get_field_expr(field_python_name, value)
            fields[field] = field_expr

    if transaction_kwargs:
        bad_args = "', '".join(transaction_kwargs)
        logger.error(f"unexpected keyword arguments: '{bad_args}'", location=location)

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
    last_log = BytesExpressionBuilder(itxn_tmp.get_field_value(TxnFields.last_log, location))
    abi_result = ARC4FromLogBuilder.abi_expr_from_log(signature_return_type, last_log, location)
    # the declared result wtype may be different to the arc4 signature return wtype
    # due to automatic conversion of ARC4 -> native types
    if declared_result_type != signature_return_type:
        abi_result = ARC4Decode(
            value=abi_result, wtype=declared_result_type.wtype, source_location=location
        )

    abi_result_builder = builder_for_instance(declared_result_type, abi_result)
    return TupleLiteralBuilder((abi_result_builder, itxn_tmp), location)


def _combine_locs(exprs: Sequence[Expression]) -> SourceLocation:
    return reduce(operator.add, (a.source_location for a in exprs))


def _arc4_tuple_from_items(
    items: Sequence[awst_nodes.Expression], source_location: SourceLocation
) -> awst_nodes.ARC4Encode:
    # TODO: should we just allow TuplExpression to have an ARCTuple wtype?
    args_tuple = awst_nodes.TupleExpression.from_items(items, source_location)
    return awst_nodes.ARC4Encode(
        value=args_tuple,
        wtype=wtypes.ARC4Tuple(args_tuple.wtype.types, source_location),
        source_location=source_location,
    )
