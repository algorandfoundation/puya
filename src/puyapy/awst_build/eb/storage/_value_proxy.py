import typing

import typing_extensions

from puya.awst.nodes import Expression, Statement
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb._base import (
    InstanceExpressionBuilder,
)
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    NodeBuilder,
)

_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)
_TExpression_co = typing_extensions.TypeVar(
    "_TExpression_co", bound=Expression, default=Expression, covariant=True
)


class ValueProxyExpressionBuilder(InstanceExpressionBuilder[_TPyType_co, _TExpression_co]):
    def __init__(self, typ: _TPyType_co, expr: _TExpression_co):
        super().__init__(typ, expr)

    @property
    def _proxied(self) -> InstanceBuilder:
        return builder_for_instance(self.pytype, self.resolve())

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return self._proxied.to_bytes(location)

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
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._proxied.contains(item, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return self._proxied.compare(other, op, location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        return self._proxied.binary_op(other, op, location, reverse=reverse)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        return self._proxied.augmented_assignment(op, rhs, location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._proxied.index(index, location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        return self._proxied.slice_index(begin_index, end_index, stride, location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        return self._proxied.member_access(name, location)

    @typing.override
    def iterate(self) -> Expression:
        return self._proxied.iterate()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self._proxied.iterable_item_type()
