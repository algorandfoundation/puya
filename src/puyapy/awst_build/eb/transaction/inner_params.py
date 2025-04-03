import abc
import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import (
    Copy,
    CreateInnerTransaction,
    Expression,
    SubmitInnerTransaction,
    UInt64Constant,
    UpdateInnerTransaction,
)
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._utils import constant_bool_and_error
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.transaction.inner import InnerTransactionExpressionBuilder
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS

logger = log.get_logger(__name__)


class InnerTxnParamsTypeBuilder(TypeBuilder[pytypes.InnerTransactionFieldsetType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        transaction_fields = dict[TxnField, Expression]()
        transaction_fields[TxnField.Fee] = UInt64Constant(
            value=0, source_location=self.source_location
        )
        typ = self.produces()
        if typ.transaction_type is not None:
            transaction_fields[TxnField.TypeEnum] = UInt64Constant(
                value=typ.transaction_type.value,
                teal_alias=typ.transaction_type.name,
                source_location=self.source_location,
            )
        transaction_fields.update(_map_itxn_args(arg_names, args))

        create_expr = CreateInnerTransaction(
            fields=transaction_fields, wtype=typ.wtype, source_location=location
        )
        return InnerTxnParamsExpressionBuilder(typ, create_expr)


class InnerTxnParamsExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.InnerTransactionFieldsetType]
):
    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError("cannot serialize inner transaction fieldset", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "submit":
            return _Submit(self, location)
        elif name == "set":
            return _Set(self, location)
        elif name == "copy":
            return _Copy(self, location)
        return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


class _MemberFunction(FunctionBuilder, abc.ABC):
    def __init__(self, base: InnerTxnParamsExpressionBuilder, location: SourceLocation) -> None:
        super().__init__(location)
        self.base = base


class _Submit(_MemberFunction):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        result_typ = pytypes.InnerTransactionResultTypes[self.base.pytype.transaction_type]
        submit_expr = SubmitInnerTransaction(itxns=[self.base.resolve()], source_location=location)
        return InnerTransactionExpressionBuilder(submit_expr, result_typ)


class _Copy(_MemberFunction):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        copy_expr = Copy(value=self.base.resolve(), source_location=location)
        return InnerTxnParamsExpressionBuilder(self.base.pytype, copy_expr)


class _Set(_MemberFunction):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        transaction_fields = _map_itxn_args(arg_names, args)
        update_expr = UpdateInnerTransaction(
            itxn=self.base.resolve(), fields=transaction_fields, source_location=location
        )
        return NoneExpressionBuilder(update_expr)


def _map_itxn_args(
    arg_names: list[str | None], args: Sequence[NodeBuilder]
) -> dict[TxnField, Expression]:
    transaction_fields = dict[TxnField, Expression]()
    for arg_name, arg in zip(arg_names, args, strict=True):
        if arg_name is None:
            logger.error("unexpected positional argument", location=arg.source_location)
        elif (params := PYTHON_ITXN_ARGUMENTS.get(arg_name)) is None:
            logger.error("unrecognised keyword argument", location=arg.source_location)
        else:
            transaction_fields[params.field] = params.validate_and_convert(arg).resolve()
    return transaction_fields
