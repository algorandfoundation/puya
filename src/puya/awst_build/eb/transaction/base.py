import abc
import typing

from puya.awst.nodes import Expression
from puya.awst.txn_fields import TxnField
from puya.awst_build import pytypes
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._utils import constant_bool_and_error
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.transaction.fields import PYTHON_TXN_FIELDS
from puya.errors import CodeError
from puya.parse import SourceLocation


class BaseTransactionExpressionBuilder(NotIterableInstanceExpressionBuilder, abc.ABC):
    @typing.override
    @typing.final
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError("cannot serialize transaction type", location)

    @abc.abstractmethod
    def get_field_value(self, field: TxnField, location: SourceLocation) -> Expression: ...

    @abc.abstractmethod
    def get_array_member(
        self, field: TxnField, typ: pytypes.PyType, location: SourceLocation
    ) -> NodeBuilder: ...

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        field_data = PYTHON_TXN_FIELDS.get(name)
        if field_data is None:
            return super().member_access(name, location)
        field, typ = field_data.field, field_data.type
        if field.is_array:
            return self.get_array_member(field, typ, location)
        else:
            field_expr = self.get_field_value(field, location)
            return builder_for_instance(typ, field_expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)
