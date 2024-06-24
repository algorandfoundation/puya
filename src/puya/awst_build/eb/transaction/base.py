import abc
import typing

from puya.awst.nodes import TXN_FIELDS, Expression, TxnField
from puya.awst_build import pytypes
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.transaction.fields import get_field_python_name
from puya.errors import CodeError
from puya.parse import SourceLocation

_PYTHON_MEMBER_FIELD_MAP = {
    get_field_python_name(f): (f, pytypes.from_basic_wtype(f.wtype)) for f in TXN_FIELDS
}


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

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        field_data = _PYTHON_MEMBER_FIELD_MAP.get(name)
        if field_data is None:
            return super().member_access(name, location)
        field, typ = field_data
        if field.is_array:
            return self.get_array_member(field, typ, location)
        else:
            expr = self.get_field_value(field, location)
            return builder_for_instance(typ, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)
