from __future__ import annotations

import typing

from puya.awst.nodes import (
    Expression,
    InnerTransactionField,
    SubmitInnerTransaction,
    TxnField,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import (
    FunctionBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.transaction.base import BaseTransactionExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.utils import expect_operand_type, require_instance_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build.constants import TransactionType
    from puya.parse import SourceLocation


class InnerTransactionTypeBuilder(TypeBuilder[pytypes.TransactionRelatedType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> typing.Never:
        typ = self.produces()
        params_typ = pytypes.InnerTransactionFieldsetTypes[typ.transaction_type]
        raise CodeError(
            f"{typ} cannot be instantiated directly, create a {params_typ} and submit instead",
            location,
        )


class InnerTransactionExpressionBuilder(BaseTransactionExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.TransactionRelatedType)
        super().__init__(typ, expr)

    def get_field_value(self, field: TxnField, location: SourceLocation) -> Expression:
        return InnerTransactionField(
            itxn=self.resolve(),
            field=field,
            source_location=location,
            wtype=field.wtype,
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
        match args:
            case [NodeBuilder() as eb]:
                index_expr = expect_operand_type(eb, pytypes.UInt64Type).resolve()
                expr = InnerTransactionField(
                    itxn=self.transaction,
                    field=self.field,
                    array_index=index_expr,
                    wtype=self.typ.wtype,
                    source_location=location,
                )
                return builder_for_instance(self.typ, expr)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


def _get_transaction_type_from_arg(builder: InstanceBuilder) -> TransactionType | None:
    if (
        isinstance(builder.pytype, pytypes.TransactionRelatedType)
        and builder.pytype in pytypes.InnerTransactionFieldsetTypes.values()
    ):
        return builder.pytype.transaction_type
    raise CodeError("Expected an InnerTxnParams argument", builder.source_location)


class SubmitInnerTransactionExpressionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if len(args) > 1:
            arg_exprs = []
            result_types = []
            for arg in args:
                arg_inst = require_instance_builder(arg)
                arg_exprs.append(arg_inst.resolve())
                arg_txn_type = _get_transaction_type_from_arg(arg_inst)
                arg_result_type = pytypes.InnerTransactionResultTypes[arg_txn_type]
                result_types.append(arg_result_type)
            result_typ = pytypes.GenericTupleType.parameterise(result_types, location)
            return TupleExpressionBuilder(
                SubmitInnerTransaction(
                    itxns=tuple(arg_exprs), wtype=result_typ.wtype, source_location=location
                ),
                result_typ,
            )
        raise CodeError("submit_txns must be called with 2 or more parameters")
