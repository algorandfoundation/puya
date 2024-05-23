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
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.transaction.base import BaseTransactionExpressionBuilder, expect_wtype
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build import pytypes
    from puya.awst_build.constants import TransactionType
    from puya.parse import SourceLocation


class InnerTransactionArrayExpressionBuilder(IntermediateExpressionBuilder):
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
        match args:
            case [(ExpressionBuilder() | Literal(value=int())) as eb]:
                index_expr = expect_operand_wtype(eb, wtypes.uint64_wtype)
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


class InnerTransactionExpressionBuilder(BaseTransactionExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType | None = None):  # TODO
        self.pytyp = typ
        self.wtype = expect_wtype(expr, wtypes.WInnerTransaction)
        super().__init__(expr)

    def get_field_value(self, field: TxnField, location: SourceLocation) -> Expression:
        return InnerTransactionField(
            itxn=self.expr,
            field=field,
            source_location=location,
            wtype=field.wtype,
        )

    def get_array_member(
        self, field: TxnField, typ: pytypes.PyType, location: SourceLocation
    ) -> ExpressionBuilder:
        return InnerTransactionArrayExpressionBuilder(self.expr, field, typ, location)


class InnerTransactionClassExpressionBuilder(TypeClassExpressionBuilder[wtypes.WInnerTransaction]):
    def __init__(self, location: SourceLocation, wtype: wtypes.WInnerTransaction):
        super().__init__(wtype, location)
        self.wtype = wtype

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
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
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if len(args) > 1:
            transaction_types = {a: _get_transaction_type_from_arg(a) for a in args}
            return TupleExpressionBuilder(
                SubmitInnerTransaction(
                    wtype=wtypes.WTuple(
                        (wtypes.WInnerTransaction.from_type(transaction_types[a]) for a in args),
                        location,
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
