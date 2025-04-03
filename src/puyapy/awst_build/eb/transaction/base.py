import abc
import typing
from collections.abc import Sequence

from puya.awst.nodes import Expression
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._utils import constant_bool_and_error
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.transaction.txn_fields import PYTHON_TXN_FIELDS, PythonTxnField


class BaseTransactionExpressionBuilder(NotIterableInstanceExpressionBuilder, abc.ABC):
    @typing.override
    @typing.final
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError("cannot serialize transaction type", location)

    @abc.abstractmethod
    def get_field_value(
        self, field: TxnField, typ: pytypes.RuntimeType, location: SourceLocation
    ) -> InstanceBuilder: ...

    @abc.abstractmethod
    def get_array_field_value(
        self,
        field: TxnField,
        typ: pytypes.RuntimeType,
        index: InstanceBuilder,
        location: SourceLocation,
    ) -> InstanceBuilder: ...

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        field_data = PYTHON_TXN_FIELDS.get(name)
        if field_data is None:
            return super().member_access(name, location)
        if field_data.field.is_array:
            return _ArrayItem(base=self, field_data=field_data, location=location)
        else:
            return self.get_field_value(field_data.field, field_data.type, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


class _ArrayItem(FunctionBuilder):
    def __init__(
        self,
        base: BaseTransactionExpressionBuilder,
        field_data: PythonTxnField,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.base = base
        self.field_data = field_data

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(
            args,
            pytypes.UInt64Type,
            location,
            resolve_literal=True,
        )
        return self.base.get_array_field_value(
            self.field_data.field, self.field_data.type, arg, location
        )
