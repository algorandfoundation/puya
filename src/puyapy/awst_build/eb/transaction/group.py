import typing
from collections.abc import Sequence

import mypy.nodes
from puya import algo_constants, log
from puya.awst import wtypes
from puya.awst.nodes import Expression, GroupTransactionReference, IntrinsicCall, UInt64Constant
from puya.awst.txn_fields import TxnField
from puya.parse import SourceLocation

from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.transaction.base import BaseTransactionExpressionBuilder

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
                txn = GroupTransactionReference(
                    index=group_index, wtype=wtype, source_location=location
                )
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
        txn = GroupTransactionReference(index=group_index, wtype=wtype, source_location=location)
        return GroupTransactionExpressionBuilder(txn, typ)


class GroupTransactionExpressionBuilder(BaseTransactionExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.TransactionRelatedType)
        super().__init__(typ, expr)

    @typing.override
    def get_field_value(
        self, field: TxnField, typ: pytypes.PyType, location: SourceLocation
    ) -> InstanceBuilder:
        assert not field.is_array
        assert typ.wtype.scalar_type == field.avm_type
        expr = IntrinsicCall(  # TODO: use (+rename) InnerTransactionField
            op_code="gtxns",
            immediates=[field.immediate],
            stack_args=[self.resolve()],
            wtype=typ.wtype,
            source_location=location,
        )
        return builder_for_instance(typ, expr)

    @typing.override
    def get_array_field_value(
        self,
        field: TxnField,
        typ: pytypes.PyType,
        index: InstanceBuilder,
        location: SourceLocation,
    ) -> InstanceBuilder:
        assert field.is_array
        assert index.pytype == pytypes.UInt64Type
        assert typ.wtype.scalar_type == field.avm_type
        expr = IntrinsicCall(
            op_code="gtxnsas",
            immediates=[field.immediate],
            stack_args=[self.resolve(), index.resolve()],
            wtype=typ.wtype,
            source_location=location,
        )
        return builder_for_instance(typ, expr)
