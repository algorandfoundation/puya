import typing

from puya.awst.nodes import Expression, Literal, Statement
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
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
    def _proxied(self) -> InstanceBuilder:
        return builder_for_instance(self.pytype, self.expr)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        return self._proxied.delete(location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return self._proxied.bool_eval(location, negate=negate)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        return self._proxied.unary_op(op, location)

    @typing.override
    def contains(
        self, item: InstanceBuilder | Literal, location: SourceLocation
    ) -> InstanceBuilder:
        return self._proxied.contains(item, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return self._proxied.compare(other, op, location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        return self._proxied.binary_op(other, op, location, reverse=reverse)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder | Literal, location: SourceLocation
    ) -> Statement:
        return self._proxied.augmented_assignment(op, rhs, location)

    @typing.override
    def index(self, index: InstanceBuilder | Literal, location: SourceLocation) -> InstanceBuilder:
        return self._proxied.index(index, location)

    @typing.override
    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        return self._proxied.slice_index(begin_index, end_index, stride, location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        return self._proxied.member_access(name, location)

    @typing.override
    def iterate(self) -> Iteration:
        return self._proxied.iterate()
