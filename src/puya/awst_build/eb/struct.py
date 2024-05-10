from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import Expression, FieldExpression, Literal
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError
from puya.parse import SourceLocation


class StructSubclassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, wtype: wtypes.WStructType, location: SourceLocation):
        super().__init__(location=location)
        self.wtype = wtype

    def produces(self) -> wtypes.WType:
        return self.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        raise NotImplementedError


class StructExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.WStructType)
        self.wtype: wtypes.WStructType = expr.wtype
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        try:
            field_wtype = self.wtype.fields[name]
        except KeyError as ex:
            raise CodeError(f"Invalid struct field: {name}", location) from ex
        field_expr = FieldExpression(location, field_wtype, self.expr, name)
        return var_expression(field_expr)
