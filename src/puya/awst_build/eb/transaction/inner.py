import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst.nodes import Expression, InnerTransactionField, SubmitInnerTransaction, TxnField
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.transaction.base import BaseTransactionExpressionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.errors import CodeError
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
        arg = expect.exactly_one_arg_of_type_else_dummy(
            args, pytypes.UInt64Type, location, resolve_literal=True
        )
        expr = InnerTransactionField(
            itxn=self.transaction,
            field=self.field,
            array_index=arg.resolve(),
            wtype=self.typ.wtype,
            source_location=location,
        )
        return builder_for_instance(self.typ, expr)


class SubmitInnerTransactionExpressionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg_exprs = []
        result_types = []
        for arg in args:
            match arg:
                case InstanceBuilder(
                    pytype=pytypes.TransactionRelatedType() as arg_pytype
                ) if arg_pytype in pytypes.InnerTransactionFieldsetTypes.values():
                    pass
                case _:
                    raise CodeError("unexpected argument type", arg.source_location)

            arg_exprs.append(arg.resolve())
            arg_result_type = pytypes.InnerTransactionResultTypes[arg_pytype.transaction_type]
            result_types.append(arg_result_type)
        result_typ = pytypes.GenericTupleType.parameterise(result_types, location)
        return TupleExpressionBuilder(
            SubmitInnerTransaction(group=tuple(arg_exprs), source_location=location),
            result_typ,
        )
