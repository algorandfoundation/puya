import typing

from puya.awst import wtypes
from puya.awst_build.eb.base import TypeClassExpressionBuilder, ValueExpressionBuilder
from puya.errors import CodeError


class VoidTypeExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.void_wtype


class VoidExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.void_wtype

    def lvalue(self) -> typing.Never:
        raise CodeError(
            "None indicates an empty return and cannot be assigned", self.source_location
        )
