from __future__ import annotations

import abc
import typing

from puya.awst import wtypes
from puya.awst.nodes import Expression, Literal, TxnField, TxnFields
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import InternalError

if typing.TYPE_CHECKING:
    from puya.parse import SourceLocation


class BaseTransactionExpressionBuilder(ValueExpressionBuilder, abc.ABC):
    transaction_fields_mapping: typing.Final = {f.python_name: f for f in TxnFields.all_fields()}

    @abc.abstractmethod
    def get_field_value(self, field: TxnField, location: SourceLocation) -> Expression:
        ...

    @abc.abstractmethod
    def get_array_member(self, field: TxnField, location: SourceLocation) -> ExpressionBuilder:
        ...

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        try:
            field = self.transaction_fields_mapping[name]
        except KeyError:
            pass
        else:
            if field.is_array:
                return self.get_array_member(field, location)
            else:
                expr = self.get_field_value(field, location)
                return var_expression(expr)
        return super().member_access(name, location)


_WType = typing.TypeVar("_WType", bound=wtypes.WType)


def expect_wtype(expr: Expression, wtype_type: type[_WType]) -> _WType:
    if isinstance(expr.wtype, wtype_type):
        return expr.wtype
    raise InternalError(
        f"Expected expression with type {wtype_type}, received: {expr.wtype}", expr.source_location
    )
