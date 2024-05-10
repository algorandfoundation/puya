from __future__ import annotations

import operator
import typing
from functools import reduce

import attrs
import mypy.nodes
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    TXN_FIELDS_BY_IMMEDIATE,
    BytesConstant,
    BytesEncoding,
    CreateInnerTransaction,
    Expression,
    InnerTransactionField,
    Literal,
    MethodConstant,
    SingleEvaluation,
    SubmitInnerTransaction,
    TupleExpression,
    TxnField,
    TxnFields,
    UInt64Constant,
)
from puya.awst_build import constants, pytypes
from puya.awst_build.constants import TransactionType
from puya.awst_build.eb.arc4._utils import (
    ARC4Signature,
    arc4_tuple_from_items,
    expect_arc4_operand_wtype,
    get_arc4_args_and_signature,
    get_arc4_signature,
)
from puya.awst_build.eb.arc4.base import ARC4FromLogBuilder
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puya.awst_build.eb.transaction.fields import get_field_python_name
from puya.awst_build.eb.transaction.inner_params import get_field_expr
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from puya.awst_build.context import ASTConversionModuleContext
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


@attrs.frozen
class _ABICallExpr:
    method: ExpressionBuilder | Literal
    abi_args: Sequence[ExpressionBuilder | Literal]
    transaction_kwargs: dict[str, ExpressionBuilder | Literal]
    abi_arg_typs: Sequence[pytypes.PyType]


class ABICallGenericClassExpressionBuilder(GenericClassExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        return ABICallClassExpressionBuilder(None, self.source_location).call(
            args, arg_typs, arg_kinds, arg_names, location
        )

    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        try:
            (index,) = indexes
        except ValueError as ex:
            raise CodeError("Expected a single type arg", location) from ex
        match index:
            case TypeClassExpressionBuilder() as type_class:
                wtype = type_class.produces()
            case _:
                raise CodeError("Invalid type parameter", index.source_location)
        return ABICallClassExpressionBuilder(wtype, location)


class ARC4ClientClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        source_location: SourceLocation,
        type_info: mypy.nodes.TypeInfo,
    ):
        super().__init__(source_location)
        self.context = context
        self.type_info = type_info

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        return ARC4ClientMethodExpressionBuilder(self.context, self.type_info, name, location)


class ARC4ClientMethodExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        type_info: mypy.nodes.TypeInfo,
        name: str,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self.type_info = type_info
        self.name = name

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        raise CodeError(
            f"Can't invoke client methods directly, use {constants.CLS_ARC4_ABI_CALL}", location
        )


class ABICallClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, result_wtype: wtypes.WType | None, source_location: SourceLocation) -> None:
        super().__init__(source_location)
        self.result_wtype = result_wtype
        app_itxn_wtype = wtypes.WInnerTransaction.from_type(TransactionType.appl)
        if _is_typed(result_wtype):
            self.wtype: wtypes.WInnerTransaction | wtypes.WTuple = wtypes.WTuple(
                (result_wtype, app_itxn_wtype), source_location
            )
        else:
            self.wtype = app_itxn_wtype

    def produces(self) -> wtypes.WType:
        return self.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        abi_call_expr = _extract_abi_call_args(args, arg_typs, arg_kinds, arg_names, location)
        method = abi_call_expr.method

        result_wtype = self.result_wtype
        match method:
            case Literal(value=str(method_str)):
                arc4_args, signature = get_arc4_args_and_signature(
                    method_str, abi_call_expr.abi_arg_typs, abi_call_expr.abi_args, location
                )
                if result_wtype is not None:
                    # this will be validated against signature below, by comparing
                    # the generated method_selector against the supplied method_str
                    signature = attrs.evolve(
                        signature,
                        # TODO: remove this HACK
                        return_type=pytypes._builtins_registry.get(result_wtype.stub_name)
                        or pytypes.ARC4DynamicBytesType,
                    )
                elif signature.return_type is None:
                    signature = attrs.evolve(signature, return_type=pytypes.NoneType)
                if not signature.method_selector.startswith(method_str):
                    raise CodeError(
                        f"Method selector from args '{signature.method_selector}' "
                        f"does not match provided method selector: '{method_str}'",
                        method.source_location,
                    )
            case (
                ARC4ClientMethodExpressionBuilder() | BaseClassSubroutineInvokerExpressionBuilder()
            ) as eb:  # TODO: can probably use func type from arg_typs now
                signature = get_arc4_signature(eb.context, eb.type_info, eb.name, location)
                result_wtype = (
                    signature.return_type.wtype if signature.return_type is not None else None
                )
                num_args = len(abi_call_expr.abi_args)
                num_types = len(signature.arg_types)
                if num_types != num_args:
                    raise CodeError(
                        f"Number of arguments ({num_args})"
                        f" does not match signature ({num_types})",
                        location,
                    )
                arc4_args = [
                    expect_arc4_operand_wtype(arg, pt.wtype)
                    for arg, pt in zip(abi_call_expr.abi_args, signature.arg_types, strict=True)
                ]
            case _:
                raise CodeError(
                    "First argument must be a `str` value of an ARC4 method name/selector",
                    location,
                )

        return var_expression(
            _create_abi_call_expr(
                signature,
                arc4_args,
                abi_call_expr.transaction_kwargs,
                location,
                return_inner_txn_only=not _is_typed(result_wtype),
            )
        )


def _is_typed(wtype: wtypes.WType | None) -> typing.TypeGuard[wtypes.WType]:
    return wtype is not None and wtype is not wtypes.void_wtype


def _create_abi_call_expr(
    signature: ARC4Signature,
    abi_args: Sequence[Expression],
    transaction_kwargs: dict[str, ExpressionBuilder | Literal],
    location: SourceLocation,
    *,
    return_inner_txn_only: bool,
) -> Expression:
    if signature.return_type is None:
        raise InternalError("Expected ARC4Signature.return_type to be defined", location)
    abi_arg_exprs: list[Expression] = [
        MethodConstant(
            value=signature.method_selector,
            source_location=location,
        )
    ]
    asset_exprs = list[Expression]()
    account_exprs = list[Expression]()
    application_exprs = list[Expression]()

    def append_ref_arg(ref_list: list[Expression], arg_expr: Expression) -> None:
        # asset refs start at 0, account and application start at 1
        implicit_offset = 0 if ref_list is asset_exprs else 1
        # TODO: what about references that are used more than once?
        ref_index = len(ref_list)
        ref_list.append(arg_expr)
        abi_arg_exprs.append(
            BytesConstant(
                value=(ref_index + implicit_offset).to_bytes(length=1),
                encoding=BytesEncoding.base16,
                source_location=arg_expr.source_location,
            )
        )

    for arg_expr, pytyp in zip(abi_args, signature.arg_types, strict=True):
        match pytyp.wtype:
            case wtypes.ARC4Type():
                abi_arg_exprs.append(arg_expr)
            case wtypes.asset_wtype:
                append_ref_arg(asset_exprs, arg_expr)
            case wtypes.account_wtype:
                append_ref_arg(account_exprs, arg_expr)
            case wtypes.application_wtype:
                append_ref_arg(application_exprs, arg_expr)
            case wtypes.WGroupTransaction():
                raise CodeError(
                    "Transaction arguments are not supported for contract to contract calls",
                    arg_expr.source_location,
                )
            case _:
                raise CodeError("Invalid argument type", arg_expr.source_location)

    fields: dict[TxnField, Expression] = {
        TxnFields.fee: UInt64Constant(
            value=0,
            source_location=location,
        ),
        TxnFields.type: UInt64Constant(
            value=constants.TransactionType.appl.value,
            teal_alias=constants.TransactionType.appl.name,
            source_location=location,
        ),
    }
    if len(abi_arg_exprs) > 15:
        packed_arg_slice = slice(15, None)
        args_to_pack = abi_arg_exprs[packed_arg_slice]
        abi_arg_exprs[packed_arg_slice] = [
            arc4_tuple_from_items(args_to_pack, _combine_locs(args_to_pack))
        ]

    _add_array_exprs(fields, TxnFields.app_args, abi_arg_exprs)
    _add_array_exprs(fields, TxnFields.accounts, account_exprs)
    _add_array_exprs(fields, TxnFields.apps, application_exprs)
    _add_array_exprs(fields, TxnFields.assets, asset_exprs)
    for field_python_name, field in _APP_TRANSACTION_FIELDS.items():
        try:
            value = transaction_kwargs.pop(field_python_name)
        except KeyError:
            continue
        field, field_expr = get_field_expr(field_python_name, value)
        fields[field] = field_expr

    if transaction_kwargs:
        bad_args = "', '".join(transaction_kwargs)
        raise CodeError(f"Unknown arguments: '{bad_args}'", location)

    create_itxn = CreateInnerTransaction(
        fields=fields,
        wtype=wtypes.WInnerTransactionFields.from_type(constants.TransactionType.appl),
        source_location=location,
    )
    itxn = SubmitInnerTransaction(
        itxns=(create_itxn,),
        source_location=location,
        wtype=wtypes.WInnerTransaction.from_type(constants.TransactionType.appl),
    )

    if return_inner_txn_only:
        return itxn
    itxn_tmp = SingleEvaluation(itxn)
    last_log = InnerTransactionField(
        source_location=location,
        itxn=itxn_tmp,
        field=TxnFields.last_log,
        wtype=TxnFields.last_log.wtype,
    )
    return TupleExpression.from_items(
        (
            ARC4FromLogBuilder.abi_expr_from_log(signature.return_type.wtype, last_log, location),
            itxn_tmp,
        ),
        location,
    )


def _add_array_exprs(
    fields: dict[TxnField, Expression], field: TxnField, exprs: list[Expression]
) -> None:
    if exprs:
        fields[field] = TupleExpression.from_items(exprs, _combine_locs(exprs))


def _combine_locs(exprs: Sequence[Expression]) -> SourceLocation:
    return reduce(operator.add, (a.source_location for a in exprs))


def _extract_abi_call_args(
    args: Sequence[ExpressionBuilder | Literal],
    arg_typs: Sequence[pytypes.PyType],
    arg_kinds: list[mypy.nodes.ArgKind],
    arg_names: list[str | None],
    location: SourceLocation,
) -> _ABICallExpr:
    method: ExpressionBuilder | Literal | None = None
    abi_args = list[ExpressionBuilder | Literal]()
    kwargs = dict[str, ExpressionBuilder | Literal]()
    abi_arg_typs = []
    for i in range(len(args)):
        arg_kind = arg_kinds[i]
        arg_name = arg_names[i]
        arg = args[i]

        if arg_kind == mypy.nodes.ArgKind.ARG_POS and i == 0:
            method = arg
        elif arg_kind == mypy.nodes.ArgKind.ARG_POS:
            abi_args.append(arg)
            abi_arg_typs.append(arg_typs[i])
        elif arg_kind == mypy.nodes.ArgKind.ARG_NAMED:
            if arg_name is None:
                raise InternalError(f"Expected named argument at pos {i}", location)
            kwargs[arg_name] = arg
        else:
            raise CodeError(f"Unexpected argument kind for '{arg_name}'", location)
    if method is None:
        raise CodeError("Missing required method positional argument", location)
    return _ABICallExpr(
        method=method, abi_args=abi_args, transaction_kwargs=kwargs, abi_arg_typs=abi_arg_typs
    )
