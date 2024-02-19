from __future__ import annotations

import typing

from puya.awst import wtypes
from puya.awst.nodes import (
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
from puya.awst_build.eb.transaction.base import expect_wtype
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


_parameter_mapping: typing.Final = {
    f.python_name: f for f in TxnFields.inner_transaction_param_fields()
}


def get_field_exprs(
    arg_name: str, arg: ExpressionBuilder | Literal
) -> tuple[TxnField, Expression]:
    try:
        field = _parameter_mapping[arg_name]
    except KeyError as ex:
        raise CodeError(f"{arg_name} is not a valid keyword argument", arg.source_location) from ex
    if field in (TxnFields.approval_program, TxnFields.clear_state_program):
        field = (
            TxnFields.approval_program_pages
            if field == TxnFields.approval_program
            else TxnFields.clear_state_program_pages
        )
        match arg:
            case ValueExpressionBuilder(
                wtype=wtypes.WTuple(types=tuple_item_types) as wtype
            ) if all(field.valid_type(t) for t in tuple_item_types):
                expr = expect_operand_wtype(arg, wtype)
                return field, expr
            case _:
                field_expr = expect_operand_wtype(arg, field.wtype)
    elif field.is_array:
        match arg:
            case ValueExpressionBuilder(
                wtype=wtypes.WTuple(types=tuple_item_types) as wtype
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


class InnerTxnParamsClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, source_location: SourceLocation, wtype: wtypes.WInnerTransactionFields):
        super().__init__(source_location)
        self.wtype = wtype

    def produces(self) -> wtypes.WInnerTransactionFields:
        return self.wtype

    def call(
        self,
        args: typing.Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        transaction_fields = dict[TxnField, Expression]()
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
            field, expression = get_field_exprs(arg_name, arg)
            transaction_fields[field] = expression
        return var_expression(
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
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        if not args:
            return var_expression(
                SubmitInnerTransaction(
                    wtype=wtypes.WInnerTransaction.from_type(self.wtype.transaction_type),
                    itxns=(self.expr,),
                    source_location=location,
                )
            )
        raise CodeError(f"Unexpected arguments for {self.expr}", location)


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
        original_expr: mypy.nodes.CallExpr,
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
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        if None in arg_names:
            raise CodeError(
                "Positional arguments are not supported when setting transaction parameters",
                location,
            )
        transaction_fields = dict[TxnField, Expression]()
        for arg_name, arg in zip(arg_names, args, strict=True):
            assert arg_name is not None
            field, expression = get_field_exprs(arg_name, arg)
            transaction_fields[field] = expression
        return var_expression(
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
