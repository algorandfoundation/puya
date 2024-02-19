from __future__ import annotations

import typing
from typing import Sequence

from puya.awst import wtypes
from puya.awst.nodes import (
    Expression,
    InnerTransactionField,
    Literal,
    SubmitInnerTransaction,
    TxnField,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.transaction.base import (
    BaseTransactionExpressionBuilder,
    expect_wtype,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    import mypy.nodes

    from puya.awst_build.constants import TransactionType
    from puya.parse import SourceLocation


class InnerTransactionArrayExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        transaction: Expression,
        field: TxnField,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.transaction = transaction
        self.field = field

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [(ExpressionBuilder() | Literal(value=int())) as eb]:
                index_expr = expect_operand_wtype(eb, wtypes.uint64_wtype)
                expr = InnerTransactionField(
                    source_location=location,
                    wtype=self.field.wtype,
                    itxn=self.transaction,
                    field=self.field,
                    array_index=index_expr,
                )
                return var_expression(expr)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class InnerTransactionExpressionBuilder(BaseTransactionExpressionBuilder):
    def __init__(self, expr: Expression):
        self.wtype = expect_wtype(expr, wtypes.WInnerTransaction)
        super().__init__(expr)

    def get_field_value(self, field: TxnField, location: SourceLocation) -> Expression:
        return InnerTransactionField(
            itxn=self.expr,
            field=field,
            source_location=location,
            wtype=field.wtype,
        )

    def get_array_member(self, field: TxnField, location: SourceLocation) -> ExpressionBuilder:
        return InnerTransactionArrayExpressionBuilder(self.expr, field, location)


class InnerTransactionClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.WInnerTransaction):
        super().__init__(location)
        self.wtype = wtype

    def produces(self) -> wtypes.WType:
        return self.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> typing.Never:
        params_wtype = wtypes.WInnerTransactionFields.from_type(self.wtype.transaction_type)
        raise CodeError(
            f"{self.wtype} cannot be instantiated directly, "
            f"create a {params_wtype} and submit instead",
            location,
        )


def _get_transaction_type_from_arg(
    literal_or_expr: ExpressionBuilder | Literal,
) -> TransactionType | None:
    if isinstance(literal_or_expr, ExpressionBuilder):
        wtype = literal_or_expr.rvalue().wtype
        if isinstance(wtype, wtypes.WInnerTransactionFields):
            return wtype.transaction_type
    raise CodeError("Expected an InnerTxnParams argument", literal_or_expr.source_location)


class SubmitInnerTransactionExpressionBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        if len(args) > 1:
            transaction_types = {a: _get_transaction_type_from_arg(a) for a in args}
            return var_expression(
                SubmitInnerTransaction(
                    wtype=wtypes.WTuple.from_types(
                        wtypes.WInnerTransaction.from_type(transaction_types[a]) for a in args
                    ),
                    itxns=tuple(
                        expect_operand_wtype(
                            a, wtypes.WInnerTransactionFields.from_type(transaction_types[a])
                        )
                        for a in args
                    ),
                    source_location=location,
                )
            )
        raise CodeError("submit_txns must be called with 2 or more parameters")
