import typing

from puya.awst.nodes import (
    BinaryBooleanOperator,
    ConditionalExpression,
    Expression,
    Lvalue,
    Statement,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import coalesce
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puyapy.awst_build.utils import determine_base_type

_DeferredTypes = pytypes.UnionType | pytypes.LiteralOnlyType


class DeferredConditionalExpressionBuilder(InstanceBuilder[_DeferredTypes]):
    """
    An InstanceBuilder that handles cases where the result type is not yet resolvable to
    a WType (so a ConditionalExpression cannot be created), but might be resolvable in specific
    usage scenarios.

    Non-exhaustive examples:
        - Python literals: could be resolvable if inside a constructor, binary operator, etc
        - Union types: could be resolvable in a boolean context

    """

    def __init__(
        self,
        *,
        true: InstanceBuilder,
        false: InstanceBuilder,
        condition: InstanceBuilder,
        location: SourceLocation,
        result_type: _DeferredTypes,
    ):
        super().__init__(location)
        self._pytype = result_type
        self._true = true
        self._false = false
        self._condition = condition

    @typing.override
    @property
    def pytype(self) -> _DeferredTypes:
        return self._pytype

    @typing.override
    def resolve(self) -> Expression:
        true_expr = self._true.resolve()
        false_expr = self._false.resolve()
        condition_expr = self._condition.resolve()
        return ConditionalExpression(
            condition=condition_expr,
            true_expr=true_expr,
            false_expr=false_expr,
            source_location=self.source_location,
        )

    @typing.override
    def resolve_literal(self, converter: LiteralConverter) -> InstanceBuilder:
        true = self._true.resolve_literal(converter)
        false = self._false.resolve_literal(converter)
        return self._evolve_builders(true=true, false=false)

    @typing.override
    def try_resolve_literal(self, converter: LiteralConverter) -> InstanceBuilder | None:
        true = self._true.try_resolve_literal(converter)
        false = self._false.try_resolve_literal(converter)
        if true is None or false is None:
            return None
        return self._evolve_builders(true=true, false=false)

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        condition = self._condition.single_eval()
        true = self._true.single_eval()
        false = self._false.single_eval()
        return DeferredConditionalExpressionBuilder(
            true=true,
            false=false,
            condition=condition,
            result_type=self._pytype,
            location=self.source_location,
        )

    def _evolve_builders(
        self,
        *,
        true: InstanceBuilder,
        false: InstanceBuilder,
        condition: InstanceBuilder | None = None,
        location: SourceLocation | None = None,
    ) -> InstanceBuilder:
        location = coalesce(location, self.source_location)
        condition = coalesce(condition, self._condition)
        return conditional_expression_builder(
            true=true, false=false, condition=condition, location=location
        )

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        true = self._true.unary_op(op, location)
        false = self._false.unary_op(op, location)
        return self._evolve_builders(true=true, false=false, location=location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.single_eval()
        true = self._true.compare(other, op, location)
        if true is NotImplemented:
            true = other.compare(self._true, op.reversed(), location)
        false = self._false.compare(other, op, location)
        if false is NotImplemented:
            false = other.compare(self._false, op.reversed(), location)
        if true is NotImplemented or false is NotImplemented:
            return NotImplemented
        return self._evolve_builders(true=true, false=false, location=location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        other = other.single_eval()
        true = self._true.binary_op(other, op, location, reverse=reverse)
        if true is NotImplemented:
            true = other.binary_op(self._true, op, location, reverse=not reverse)
        false = self._false.binary_op(other, op, location, reverse=reverse)
        if false is NotImplemented:
            false = other.binary_op(self._false, op, location, reverse=not reverse)
        if true is NotImplemented or false is NotImplemented:
            return NotImplemented
        return self._evolve_builders(true=true, false=false, location=location)

    @typing.override
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        return super().bool_binary_op(other, op, location)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        true_expr = self._true.to_bytes(location)
        false_expr = self._false.to_bytes(location)
        condition_expr = self._condition.resolve()
        return ConditionalExpression(
            condition=condition_expr,
            true_expr=true_expr,
            false_expr=false_expr,
            source_location=location,
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        true = self._true.member_access(name, location)
        false = self._false.member_access(name, location)
        if not (isinstance(true, InstanceBuilder) and isinstance(false, InstanceBuilder)):
            raise CodeError("unsupported member access on conditional expression", location)
        return self._evolve_builders(true=true, false=false)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        true = self._true.bool_eval(location, negate=negate)
        false = self._false.bool_eval(location, negate=negate)
        return self._evolve_builders(true=true, false=false, location=location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        item = item.single_eval()
        true = self._true.contains(item, location)
        false = self._false.contains(item, location)
        return self._evolve_builders(true=true, false=false, location=location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        index = index.single_eval()
        true = self._true.index(index, location)
        false = self._false.index(index, location)
        return self._evolve_builders(true=true, false=false, location=location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        if begin_index is not None:
            begin_index = begin_index.single_eval()
        if end_index is not None:
            end_index = end_index.single_eval()
        if stride is not None:
            stride = stride.single_eval()
        true = self._true.slice_index(
            begin_index=begin_index, end_index=end_index, stride=stride, location=location
        )
        false = self._false.slice_index(
            begin_index=begin_index, end_index=end_index, stride=stride, location=location
        )
        return self._evolve_builders(true=true, false=false, location=location)

    @typing.override
    def iterate(self) -> typing.Never:
        raise CodeError(
            "iterating conditional expressions is not currently supported", self.source_location
        )

    @typing.override
    def iterable_item_type(self) -> typing.Never:
        self.iterate()

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        raise CodeError("invalid Python syntax: cannot assign to conditional expression", location)

    @typing.override
    def resolve_lvalue(self) -> Lvalue:
        raise CodeError(
            "invalid Python syntax: cannot assign to conditional expression", self.source_location
        )

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError("invalid Python syntax: cannot delete conditional expression", location)


def conditional_expression_builder(
    *,
    true: InstanceBuilder,
    false: InstanceBuilder,
    condition: InstanceBuilder,
    location: SourceLocation,
) -> InstanceBuilder:
    result_type = determine_base_type(true.pytype, false.pytype, location=location)
    if isinstance(result_type, _DeferredTypes):
        return DeferredConditionalExpressionBuilder(
            true=true,
            false=false,
            condition=condition,
            location=location,
            result_type=result_type,
        )
    resolved_expr = ConditionalExpression(
        condition=condition.resolve(),
        true_expr=true.resolve(),
        false_expr=false.resolve(),
        source_location=location,
    )
    return builder_for_instance(result_type, resolved_expr)
