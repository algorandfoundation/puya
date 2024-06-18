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
from puya.awst_build.utils import expect_operand_type
from puya.errors import CodeError
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
                        "transaction group index should be between non-negative",
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
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WGroupTransaction)
        match args:
            case [InstanceBuilder(pytype=pytypes.IntLiteralType) as arg]:
                return arg.resolve_literal(GroupTransactionTypeBuilder(typ, location))
            case [InstanceBuilder(pytype=pytypes.UInt64Type) as eb]:
                group_index = eb.resolve()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
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
            source_location=location,
            wtype=field.wtype,
            op_code="gtxns",
            immediates=[field.immediate],
            stack_args=[self.resolve()],
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
        if len(args) != 1:
            raise CodeError(f"Expected 1 argument, got {len(args)}", location)
        (arg,) = args
        index_expr = expect_operand_type(arg, pytypes.UInt64Type).resolve()
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
