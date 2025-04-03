import typing
from collections.abc import Sequence

from puya.awst.nodes import Expression, InnerTransactionField, SubmitInnerTransaction
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puyapy.awst_build.eb.transaction.base import BaseTransactionExpressionBuilder
from puyapy.awst_build.eb.tuple import TupleExpressionBuilder


class InnerTransactionTypeBuilder(TypeBuilder[pytypes.InnerTransactionResultType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
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
        assert isinstance(typ, pytypes.InnerTransactionResultType)
        super().__init__(typ, expr)

    @typing.override
    def get_field_value(
        self, field: TxnField, typ: pytypes.RuntimeType, location: SourceLocation
    ) -> InstanceBuilder:
        expr = InnerTransactionField(
            itxn=self.resolve(),
            field=field,
            wtype=typ.wtype,
            source_location=location,
        )
        return builder_for_instance(typ, expr)

    @typing.override
    def get_array_field_value(
        self,
        field: TxnField,
        typ: pytypes.RuntimeType,
        index: InstanceBuilder,
        location: SourceLocation,
    ) -> InstanceBuilder:
        assert pytypes.UInt64Type <= index.pytype
        expr = InnerTransactionField(
            itxn=self.resolve(),
            field=field,
            array_index=index.resolve(),
            wtype=typ.wtype,
            source_location=location,
        )
        return builder_for_instance(typ, expr)


class SubmitInnerTransactionExpressionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg_exprs = []
        result_types = []
        for arg in args:
            match arg:
                case InstanceBuilder(
                    pytype=pytypes.InnerTransactionFieldsetType(transaction_type=txn_type)
                ):
                    arg_exprs.append(arg.resolve())
                    arg_result_type = pytypes.InnerTransactionResultTypes[txn_type]
                    result_types.append(arg_result_type)
                case other:
                    expect.not_this_type(other, default=expect.default_raise)
        result_typ = pytypes.GenericTupleType.parameterise(result_types, location)
        return TupleExpressionBuilder(
            SubmitInnerTransaction(itxns=arg_exprs, source_location=location),
            result_typ,
        )
