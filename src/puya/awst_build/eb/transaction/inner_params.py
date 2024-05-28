from __future__ import annotations

import typing

from puya.awst import wtypes
from puya.awst.nodes import (
    INNER_PARAM_TXN_FIELDS,
    Copy,
    CreateInnerTransaction,
    Expression,
    Literal,
    SubmitInnerTransaction,
    TxnField,
    TxnFields,
    UInt64Constant,
    UpdateInnerTransaction,
)
from puya.awst_build import pytypes
from puya.awst_build.constants import TransactionType
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    FunctionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.transaction import get_field_python_name
from puya.awst_build.eb.transaction.base import expect_wtype
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import construct_from_literal, expect_operand_type
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

_parameter_mapping: typing.Final = {
    get_field_python_name(f): (f, pytypes.from_basic_wtype(f.wtype))
    for f in INNER_PARAM_TXN_FIELDS
}


def get_field_expr(arg_name: str, arg: ExpressionBuilder | Literal) -> tuple[TxnField, Expression]:
    try:
        field, field_pytype = _parameter_mapping[arg_name]
    except KeyError as ex:
        raise CodeError(f"{arg_name} is not a valid keyword argument", arg.source_location) from ex
    if remapped_field := _maybe_transform_program_field_expr(field, arg):
        return remapped_field
    elif field.is_array:
        match arg:
            case ExpressionBuilder(pytype=pytypes.TupleType(items=tuple_item_types)) if all(
                field.valid_type(t.wtype)
                for t in tuple_item_types  # TODO: revisit this re serialize
            ):
                expr = arg.rvalue()
                return field, expr
        raise CodeError(f"{arg_name} should be of type tuple[{field.type_desc}, ...]")
    elif isinstance(arg, ExpressionBuilder):
        if not (arg.value_type and field.valid_type(arg.value_type)):
            raise CodeError("bad argument type", arg.source_location)
        field_expr = arg.rvalue()
    elif isinstance(arg, Literal):
        # TODO: REMOVE HACK
        if wtypes.string_wtype in field.additional_input_wtypes and isinstance(arg.value, str):
            field_expr = construct_from_literal(arg, pytypes.StringType).rvalue()
        else:
            field_expr = construct_from_literal(arg, field_pytype).rvalue()
    else:
        typing.assert_never(arg)
    return field, field_expr


def _maybe_transform_program_field_expr(
    field: TxnField, eb: ExpressionBuilder | Literal
) -> tuple[TxnField, Expression] | None:
    match field.immediate:
        case "ApprovalProgram":
            field = TxnFields.approval_program_pages
        case "ClearStateProgram":
            field = TxnFields.clear_state_program_pages
        case _:
            return None
    if field.wtype != wtypes.bytes_wtype:
        raise InternalError(
            f"Unhandled type for program pages field: {field.wtype}", eb.source_location
        )

    match eb:
        case ExpressionBuilder(pytype=pytypes.TupleType(items=tuple_item_types)) if all(
            t == pytypes.BytesType for t in tuple_item_types  # TODO: revisit this re serialize
        ):
            expr = eb.rvalue()
        case _:
            expr = expect_operand_type(eb, pytypes.BytesType).rvalue()
    return field, expr


class InnerTxnParamsClassExpressionBuilder(
    TypeClassExpressionBuilder[pytypes.TransactionRelatedType]
):
    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        transaction_fields: dict[TxnField, Expression] = {
            TxnFields.fee: UInt64Constant(
                source_location=self.source_location,
                value=0,
            )
        }
        transaction_type = self.produces2().transaction_type
        if transaction_type:
            transaction_fields[TxnFields.type] = UInt64Constant(
                source_location=self.source_location,
                value=transaction_type.value,
                teal_alias=transaction_type.name,
            )
        for arg_name, arg in zip(arg_names, args, strict=True):
            if arg_name is None:
                raise CodeError(
                    f"Positional arguments are not supported for {self.produces()}", location
                )
            field, expression = get_field_expr(arg_name, arg)
            transaction_fields[field] = expression
        typ = self.produces2()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WInnerTransactionFields)
        return InnerTxnParamsExpressionBuilder(
            CreateInnerTransaction(
                fields=transaction_fields,
                wtype=wtype,
                source_location=location,
            ),
            typ,
        )


class InnerTxnParamsExpressionBuilder(ValueExpressionBuilder[pytypes.TransactionRelatedType]):
    def __init__(self, expr: Expression, typ: pytypes.TransactionRelatedType):
        assert isinstance(typ, pytypes.TransactionRelatedType)
        super().__init__(typ, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        if name == "submit":
            return _Submit(self.expr, self.pytype.transaction_type, location)
        elif name == "set":
            return _Set(self.expr, location)
        elif name == "copy":
            return _Copy(self.expr, self.pytype, location)
        return super().member_access(name, location)


class _Submit(FunctionBuilder):
    def __init__(
        self, expr: Expression, txn_type: TransactionType | None, location: SourceLocation
    ) -> None:
        super().__init__(location)
        self._txn_type = txn_type
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        from puya.awst_build.eb.transaction import InnerTransactionExpressionBuilder

        if args:
            raise CodeError(f"Unexpected arguments for {self.expr}", location)
        result_typ = pytypes.InnerTransactionResultTypes[self._txn_type]
        return InnerTransactionExpressionBuilder(
            SubmitInnerTransaction(
                itxns=(self.expr,),
                wtype=result_typ.wtype,
                source_location=location,
            ),
            result_typ,
        )


class _Copy(FunctionBuilder):
    def __init__(
        self, expr: Expression, typ: pytypes.TransactionRelatedType, location: SourceLocation
    ) -> None:
        super().__init__(location)
        self._typ = typ
        self.wtype = expect_wtype(expr, wtypes.WInnerTransactionFields)
        assert typ.wtype == self.wtype
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if args:
            raise CodeError(f"Unexpected arguments for {self.expr}", location)
        return InnerTxnParamsExpressionBuilder(
            Copy(
                wtype=self.wtype,
                value=self.expr,
                source_location=location,
            ),
            self._typ,
        )


class _Set(FunctionBuilder):
    def __init__(self, expr: Expression, source_location: SourceLocation):
        super().__init__(source_location)
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if None in arg_names:
            raise CodeError(
                "Positional arguments are not supported when setting transaction parameters",
                location,
            )
        transaction_fields = dict[TxnField, Expression]()
        for arg_name, arg in zip(arg_names, args, strict=True):
            assert arg_name is not None
            field, expression = get_field_expr(arg_name, arg)
            transaction_fields[field] = expression
        return VoidExpressionBuilder(
            UpdateInnerTransaction(
                itxn=self.expr,
                fields=transaction_fields,
                source_location=location,
            )
        )
