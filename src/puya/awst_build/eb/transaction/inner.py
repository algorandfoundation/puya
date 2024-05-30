from __future__ import annotations

import typing

from puya.awst import wtypes
from puya.awst.nodes import (
    Expression,
    InnerTransactionField,
    Literal,
    SubmitInnerTransaction,
    TxnField,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    FunctionBuilder,
    InstanceBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.transaction.base import BaseTransactionExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.utils import expect_operand_type
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build.constants import TransactionType
    from puya.parse import SourceLocation


class InnerTransactionClassExpressionBuilder(TypeBuilder[pytypes.TransactionRelatedType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
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
            itxn=self.expr,
            field=field,
            source_location=location,
            wtype=field.wtype,
        )

    def get_array_member(
        self, field: TxnField, typ: pytypes.PyType, location: SourceLocation
    ) -> NodeBuilder:
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
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [(NodeBuilder() | Literal(value=int())) as eb]:
                index_expr = expect_operand_type(eb, pytypes.UInt64Type).rvalue()
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


def _get_transaction_type_from_arg(
    literal_or_expr: NodeBuilder | Literal,
) -> TransactionType | None:
    if isinstance(literal_or_expr, NodeBuilder):
        wtype = literal_or_expr.rvalue().wtype
        if isinstance(wtype, wtypes.WInnerTransactionFields):
            return wtype.transaction_type
    raise CodeError("Expected an InnerTxnParams argument", literal_or_expr.source_location)


class SubmitInnerTransactionExpressionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if len(args) > 1:
            transaction_types = {a: _get_transaction_type_from_arg(a) for a in args}
            result_typ = pytypes.GenericTupleType.parameterise(
                [pytypes.InnerTransactionResultTypes[transaction_types[a]] for a in args],
                location,
            )
            return TupleExpressionBuilder(
                SubmitInnerTransaction(
                    wtype=result_typ.wtype,
                    itxns=tuple(
                        expect_operand_type(
                            a,
                            pytypes.InnerTransactionFieldsetTypes[transaction_types[a]],
                        ).rvalue()
                        for a in args
                    ),
                    source_location=location,
                ),
                result_typ,
            )
        raise CodeError("submit_txns must be called with 2 or more parameters")
