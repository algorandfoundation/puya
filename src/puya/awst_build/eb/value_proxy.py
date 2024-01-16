from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst.nodes import Literal, Statement
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    Iteration,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.parse import SourceLocation


class ValueProxyExpressionBuilder(ValueExpressionBuilder):
    @property
    def _proxied(self) -> ExpressionBuilder:
        return var_expression(self.expr)

    def delete(self, location: SourceLocation) -> Statement:
        return self._proxied.delete(location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return self._proxied.bool_eval(location, negate=negate)

    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._proxied.unary_plus(location)

    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._proxied.unary_minus(location)

    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        return self._proxied.bitwise_invert(location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._proxied.contains(item, location)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._proxied.compare(other, op, location)

    def binary_op(
        self,
        other: ExpressionBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> ExpressionBuilder:
        return self._proxied.binary_op(other, op, location, reverse=reverse)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        return self._proxied.augmented_assignment(op, rhs, location)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._proxied.index(index, location)

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        return self._proxied.slice_index(begin_index, end_index, stride, location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        return self._proxied.call(args, arg_kinds, arg_names, location, original_expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        return self._proxied.member_access(name, location)

    def iterate(self) -> Iteration:
        return self._proxied.iterate()
