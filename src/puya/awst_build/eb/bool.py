from __future__ import annotations

from typing import TYPE_CHECKING

import mypy.nodes
import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    BoolConstant,
    Literal,
    Not,
    NumericComparison,
    NumericComparisonExpression,
)
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import bool_eval, convert_literal_to_expr
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class BoolClassExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.bool_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case []:
                false = BoolConstant(value=False, source_location=location)
                return var_expression(false)
            case [arg]:
                return bool_eval(arg, location)
            case _:
                raise CodeError("Too many arguments", location=location)


class BoolExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.bool_wtype

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        if not negate:
            return self
        return BoolExpressionBuilder(Not(location, self.expr))

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        if other_expr.wtype == self.wtype:
            pass
        else:
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=NumericComparison(op.value),
            rhs=other_expr,
        )
        return var_expression(cmp_expr)
