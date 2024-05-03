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
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.transaction import get_field_python_name
from puya.awst_build.eb.transaction.base import expect_wtype
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

_parameter_mapping: typing.Final = {get_field_python_name(f): f for f in INNER_PARAM_TXN_FIELDS}


def get_field_expr(arg_name: str, arg: ExpressionBuilder | Literal) -> tuple[TxnField, Expression]:
    try:
        field = _parameter_mapping[arg_name]
    except KeyError as ex:
        raise CodeError(f"{arg_name} is not a valid keyword argument", arg.source_location) from ex
    if remapped_field := _maybe_transform_program_field_expr(field, arg):
        return remapped_field
    elif field.is_array:
        match arg:
            case ExpressionBuilder(
                value_type=wtypes.WTuple(types=tuple_item_types) as wtype
            ) if all(field.valid_type(t) for t in tuple_item_types):
                expr = expect_operand_wtype(arg, wtype)
                return field, expr
        raise CodeError(f"{arg_name} should be of type tuple[{field.type_desc}, ...]")
    elif (
        isinstance(arg, ExpressionBuilder) and arg.value_type and field.valid_type(arg.value_type)
    ):
        field_expr = arg.rvalue()
    else:
        field_expr = expect_operand_wtype(arg, field.wtype)
    return field, field_expr


def _maybe_transform_program_field_expr(
    field: TxnField, eb: ExpressionBuilder | Literal
) -> tuple[TxnField, Expression] | None:
    immediate = field.immediate
    if immediate not in ("ApprovalProgram", "ClearStateProgram"):
        return None
    field = (
        TxnFields.approval_program_pages
        if immediate == "ApprovalProgram"
        else TxnFields.clear_state_program_pages
    )
    match eb:
        case ValueExpressionBuilder(wtype=wtypes.WTuple(types=tuple_item_types) as wtype) if all(
            field.valid_type(t) for t in tuple_item_types
        ):
            expr = expect_operand_wtype(eb, wtype)
        case _:
            expr = expect_operand_wtype(eb, field.wtype)
    return field, expr


class InnerTxnParamsClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, source_location: SourceLocation, wtype: wtypes.WInnerTransactionFields):
        super().__init__(source_location)
        self.wtype = wtype

    def produces(self) -> wtypes.WInnerTransactionFields:
        return self.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
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
        transaction_type = self.wtype.transaction_type
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
        return InnerTxnParamsExpressionBuilder(
            CreateInnerTransaction(
                wtype=self.produces(),
                fields=transaction_fields,
                source_location=location,
            )
        )


class ParamsSubmitExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation) -> None:
        super().__init__(location)
        self.wtype = expect_wtype(expr, wtypes.WInnerTransactionFields)
        self.expr = expr

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        from puya.awst_build.eb.transaction import InnerTransactionExpressionBuilder

        if args:
            raise CodeError(f"Unexpected arguments for {self.expr}", location)
        return InnerTransactionExpressionBuilder(
            SubmitInnerTransaction(
                wtype=wtypes.WInnerTransaction.from_type(self.wtype.transaction_type),
                itxns=(self.expr,),
                source_location=location,
            )
        )


class CopyInnerTxnParamsExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation) -> None:
        super().__init__(location)
        self.wtype = expect_wtype(expr, wtypes.WInnerTransactionFields)
        self.expr = expr

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if not args:
            return var_expression(
                Copy(
                    wtype=self.wtype,
                    value=self.expr,
                    source_location=location,
                )
            )
        raise CodeError(f"Unexpected arguments for {self.expr}", location)


class SetInnerTxnParamsExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, source_location: SourceLocation):
        super().__init__(source_location)
        self.expr = expr

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
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


class InnerTxnParamsExpressionBuilder(ValueExpressionBuilder):
    wtype: wtypes.WInnerTransactionFields

    def __init__(self, expr: Expression):
        self.wtype = expect_wtype(expr, wtypes.WInnerTransactionFields)
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        if name == "submit":
            return ParamsSubmitExpressionBuilder(self.expr, location)
        elif name == "set":
            return SetInnerTxnParamsExpressionBuilder(self.expr, location)
        elif name == "copy":
            return CopyInnerTxnParamsExpressionBuilder(self.expr, location)
        return super().member_access(name, location)
