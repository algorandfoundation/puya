import typing
from collections.abc import Sequence

import mypy.nodes

from puya import algo_constants, log
from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    TxnField,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.transaction.base import BaseTransactionExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class GroupTransactionTypeBuilder(TypeBuilder[pytypes.TransactionRelatedType]):
    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case int(int_value):
                if int_value < 0:
                    logger.error(
                        "transaction group index should be non-negative",
                        location=literal.source_location,
                    )
                elif int_value >= algo_constants.MAX_TRANSACTION_GROUP_SIZE:
                    logger.error(
                        "transaction group index should be"
                        f" less than {algo_constants.MAX_TRANSACTION_GROUP_SIZE}",
                        location=literal.source_location,
                    )
                typ = self.produces()
                wtype = typ.wtype
                assert isinstance(wtype, wtypes.WGroupTransaction)
                group_index = UInt64Constant(value=int_value, source_location=location)
                txn = check_transaction_type(group_index, wtype, location)
                return GroupTransactionExpressionBuilder(txn, typ)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(
            args, location, default=expect.default_dummy_value(pytypes.UInt64Type)
        )
        typ = self.produces()
        if arg.pytype == pytypes.IntLiteralType:
            return arg.resolve_literal(GroupTransactionTypeBuilder(typ, location))
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WGroupTransaction)
        group_index = expect.argument_of_type_else_dummy(arg, pytypes.UInt64Type).resolve()
        txn = check_transaction_type(group_index, wtype, location)
        return GroupTransactionExpressionBuilder(txn, typ)


class GroupTransactionExpressionBuilder(BaseTransactionExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert typ == pytypes.GroupTransactionBaseType or isinstance(
            typ, pytypes.TransactionRelatedType
        )
        super().__init__(typ, expr)

    def get_field_value(self, field: TxnField, location: SourceLocation) -> Expression:
        return IntrinsicCall(  # TODO: use (+rename) InnerTransactionField
            op_code="gtxns",
            immediates=[field.immediate],
            stack_args=[self.resolve()],
            wtype=field.wtype,
            source_location=location,
        )

    def get_array_member(
        self, field: TxnField, typ: pytypes.PyType, location: SourceLocation
    ) -> NodeBuilder:
        return _ArrayItem(self.resolve(), field, typ, location)


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
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(
            args,
            pytypes.UInt64Type,
            location,
            resolve_literal=True,
        )
        expr = IntrinsicCall(
            op_code="gtxnsas",
            immediates=[self.field.immediate],
            stack_args=[self.transaction, arg.resolve()],
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
        uint64_expr = transaction_index
    else:
        index_builder = UInt64ExpressionBuilder(transaction_index).single_eval()
        runtime_type_check = NumericComparisonExpression(
            lhs=IntrinsicCall(
                op_code="gtxns",
                immediates=["TypeEnum"],
                stack_args=[index_builder.resolve()],
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
        )
        uint64_expr = CheckedMaybe.from_tuple_items(
            index_builder.resolve(),
            runtime_type_check,
            location,
            comment=f"transaction type is {expected_transaction_type.transaction_type.name}",
        )
    return ReinterpretCast(
        expr=uint64_expr, wtype=expected_transaction_type, source_location=location
    )
