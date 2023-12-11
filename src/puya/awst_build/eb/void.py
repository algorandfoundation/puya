from puya.awst import wtypes
from puya.awst.nodes import Expression
from puya.awst_build.eb.base import TypeClassExpressionBuilder, ValueExpressionBuilder
from puya.errors import CodeError


class VoidTypeExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.void_wtype


class VoidExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.void_wtype

    def build_assignment_source(self) -> Expression:
        raise CodeError(
            "None indicates an empty return and cannot be assigned",
            self.source_location,
        )
