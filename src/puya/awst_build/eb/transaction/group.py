from __future__ import annotations

import abc
import typing

from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    SingleEvaluation,
    TxnField,
    UInt64Constant,
)
from puya.awst_build import pytypes
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
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


class GroupTransactionExpressionBuilder(BaseTransactionExpressionBuilder):
    def __init__(self, expr: Expression):
        self.wtype = expect_wtype(expr, wtypes.WGroupTransaction)
        super().__init__(expr)

    def get_field_value(self, field: TxnField, location: SourceLocation) -> Expression:
        return IntrinsicCall(
            source_location=location,
            wtype=field.wtype,
            op_code="gtxns",
            immediates=[field.immediate],
            stack_args=[self.expr],
        )

    def get_array_member(self, field: TxnField, location: SourceLocation) -> ExpressionBuilder:
        return GroupTransactionArrayExpressionBuilder(self.expr, field, location)


class GroupTransactionArrayExpressionBuilder(IntermediateExpressionBuilder):
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
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if len(args) != 1:
            raise CodeError(f"Expected 1 argument, got {len(args)}", location)
        (arg,) = args
        index_expr = expect_operand_wtype(arg, wtypes.uint64_wtype)
        expr = IntrinsicCall(
            source_location=location,
            wtype=self.field.wtype,
            op_code="gtxnsas",
            immediates=[self.field.immediate],
            stack_args=[self.transaction, index_expr],
        )
        return var_expression(expr)


def check_transaction_type(
    transaction_index: Expression,
    expected_transaction_type: wtypes.WGroupTransaction,
    location: SourceLocation,
) -> Expression:
    if expected_transaction_type.transaction_type is None:
        return transaction_index
    transaction_index_tmp = SingleEvaluation(transaction_index)
    return ReinterpretCast(
        source_location=location,
        wtype=expected_transaction_type,
        expr=CheckedMaybe.from_tuple_items(
            transaction_index_tmp,
            NumericComparisonExpression(
                lhs=IntrinsicCall(
                    op_code="gtxns",
                    immediates=["TypeEnum"],
                    stack_args=[transaction_index_tmp],
                    wtype=wtypes.uint64_wtype,
                    source_location=location,
                ),
                operator=NumericComparison.eq,
                rhs=UInt64Constant(
                    value=expected_transaction_type.transaction_type.value,
                    teal_alias=expected_transaction_type.transaction_type.name,
                    source_location=location,
                ),
                source_location=location,
            ),
            location,
            comment=f"transaction type is {expected_transaction_type.transaction_type.name}",
        ),
    )


class GroupTransactionClassExpressionBuilder(TypeClassExpressionBuilder, abc.ABC):
    def __init__(self, location: SourceLocation, wtype: wtypes.WGroupTransaction):
        super().__init__(location)
        self.wtype = wtype

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
        match args:
            case [ExpressionBuilder() as eb]:
                group_index = expect_operand_wtype(eb, wtypes.uint64_wtype)
            case [Literal(value=int(int_value), source_location=loc)]:
                group_index = UInt64Constant(value=int_value, source_location=loc)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        wtype = self.wtype
        txn = (
            check_transaction_type(group_index, wtype, location)
            if isinstance(wtype, wtypes.WGroupTransaction) and wtype.transaction_type is not None
            else ReinterpretCast(expr=group_index, wtype=wtype, source_location=location)
        )
        return GroupTransactionExpressionBuilder(txn)
