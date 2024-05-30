from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst.nodes import Expression, Literal, Statement
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceExpressionBuilder,
    Iteration,
    NodeBuilder,
)
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.parse import SourceLocation


class ValueProxyExpressionBuilder(InstanceExpressionBuilder):
    def __init__(self, typ: pytypes.PyType, expr: Expression):
        super().__init__(typ, expr)

    @property
    def _proxied(self) -> NodeBuilder:
        return builder_for_instance(self.pytype, self.expr)

    def delete(self, location: SourceLocation) -> Statement:
        return self._proxied.delete(location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> NodeBuilder:
        return self._proxied.bool_eval(location, negate=negate)

    def unary_plus(self, location: SourceLocation) -> NodeBuilder:
        return self._proxied.unary_plus(location)

    def unary_minus(self, location: SourceLocation) -> NodeBuilder:
        return self._proxied.unary_minus(location)

    def bitwise_invert(self, location: SourceLocation) -> NodeBuilder:
        return self._proxied.bitwise_invert(location)

    def contains(self, item: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        return self._proxied.contains(item, location)

    def compare(
        self, other: NodeBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> NodeBuilder:
        return self._proxied.compare(other, op, location)

    def binary_op(
        self,
        other: NodeBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> NodeBuilder:
        return self._proxied.binary_op(other, op, location, reverse=reverse)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: NodeBuilder | Literal, location: SourceLocation
    ) -> Statement:
        return self._proxied.augmented_assignment(op, rhs, location)

    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        return self._proxied.index(index, location)

    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        return self._proxied.slice_index(begin_index, end_index, stride, location)

    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        return self._proxied.call(args, arg_typs, arg_kinds, arg_names, location)

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        return self._proxied.member_access(name, location)

    def iterate(self) -> Iteration:
        return self._proxied.iterate()
