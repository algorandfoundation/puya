from __future__ import annotations

import typing

from puya import algo_constants
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
from puya.awst_build.eb.base import ExpressionBuilder, FunctionBuilder, TypeClassExpressionBuilder
from puya.awst_build.eb.transaction.base import BaseTransactionExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.utils import expect_operand_type
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


class GroupTransactionClassExpressionBuilder(
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
        typ = self.produces2()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WGroupTransaction)
        match args:
            case [ExpressionBuilder() as eb]:
                group_index = expect_operand_type(eb, pytypes.UInt64Type).rvalue()
            case [Literal(value=int(int_value), source_location=loc)]:
                if int_value < 0:
                    raise CodeError(
                        "Transaction group index should be between non-negative", location
                    )
                if int_value >= algo_constants.MAX_TRANSACTION_GROUP_SIZE:
                    raise CodeError(
                        "Transaction group index should be"
                        f" less than {algo_constants.MAX_TRANSACTION_GROUP_SIZE}",
                        location,
                    )
                group_index = UInt64Constant(value=int_value, source_location=loc)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        txn = (
            check_transaction_type(group_index, wtype, location)
            if wtype.transaction_type is not None
            else ReinterpretCast(expr=group_index, wtype=wtype, source_location=location)
        )
        return GroupTransactionExpressionBuilder(txn, typ)


class GroupTransactionExpressionBuilder(BaseTransactionExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert typ == pytypes.GroupTransactionBaseType or isinstance(
            typ, pytypes.TransactionRelatedType
        )
        super().__init__(typ, expr)

    def get_field_value(self, field: TxnField, location: SourceLocation) -> Expression:
        return IntrinsicCall(  # TODO: use (+rename) InnerTransactionField
            source_location=location,
            wtype=field.wtype,
            op_code="gtxns",
            immediates=[field.immediate],
            stack_args=[self.expr],
        )

    def get_array_member(
        self, field: TxnField, typ: pytypes.PyType, location: SourceLocation
    ) -> ExpressionBuilder:
        return _ArrayItem(self.expr, field, typ, location)


class _ArrayItem(FunctionBuilder):
    def __init__(
        self,
        transaction: Expression,
        field: TxnField,
        typ: pytypes.PyType,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.typ = typ
        self.transaction = transaction
        self.field = field

    @typing.override
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
        index_expr = expect_operand_type(arg, pytypes.UInt64Type).rvalue()
        expr = IntrinsicCall(
            op_code="gtxnsas",
            immediates=[self.field.immediate],
            stack_args=[self.transaction, index_expr],
            wtype=self.typ.wtype,
            source_location=location,
        )
        return builder_for_instance(self.typ, expr)


def check_transaction_type(  # TODO: introduce GroupTransaction node and push this down to IR
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
