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
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)


class ConditionalLiteralBuilder(InstanceBuilder):
    def __init__(
        self,
        *,
        true_literal: LiteralBuilder,
        false_literal: LiteralBuilder,
        condition: InstanceBuilder,
        location: SourceLocation,
    ):
        super().__init__(location)
        self._pytype = _common_base(true_literal.pytype, false_literal.pytype, location)
        self._true_literal = true_literal
        self._false_literal = false_literal
        self._condition = condition

    @typing.override
    @property
    def pytype(self) -> pytypes.PyType:
        return self._true_literal.pytype

    @typing.override
    def resolve(self) -> Expression:
        true_expr = self._true_literal.resolve()
        false_expr = self._false_literal.resolve()
        condition_expr = self._condition.resolve()
        return ConditionalExpression(
            condition=condition_expr,
            true_expr=true_expr,
            false_expr=false_expr,
            source_location=self.source_location,
        )

    @typing.override
    def resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        true_b = converter.convert_literal(
            literal=self._true_literal, location=converter.source_location
        )
        false_b = converter.convert_literal(
            literal=self._false_literal, location=converter.source_location
        )
        return self._resolve_literals(true_b, false_b)

    @typing.override
    def try_resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder | None:
        true_b = converter.try_convert_literal(
            literal=self._true_literal, location=converter.source_location
        )
        false_b = converter.try_convert_literal(
            literal=self._false_literal, location=converter.source_location
        )
        if true_b is None or false_b is None:
            return None
        return self._resolve_literals(true_b, false_b)

    def _resolve_literals(
        self, true_b: InstanceBuilder, false_b: InstanceBuilder
    ) -> InstanceBuilder:
        result_pytype = _common_base(true_b.pytype, false_b.pytype, self.source_location)
        result_pytype = true_b.pytype
        true_expr = true_b.resolve()
        false_expr = false_b.resolve()
        condition_expr = self._condition.resolve()
        result_expr = ConditionalExpression(
            condition=condition_expr,
            true_expr=true_expr,
            false_expr=false_expr,
            source_location=self.source_location,
        )
        return builder_for_instance(result_pytype, result_expr)

    @typing.override
    def resolve_lvalue(self) -> Lvalue:
        raise CodeError("cannot assign to literal", self.source_location)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError("cannot delete literal", location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        transformed_true = self._true_literal.unary_op(op, location)
        transformed_false = self._false_literal.unary_op(op, location)
        return ConditionalLiteralBuilder(
            true_literal=transformed_true,
            false_literal=transformed_false,
            condition=self._condition,
            location=location,
        )

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.single_eval()
        transformed_true = self._true_literal.compare(other, op, location)
        transformed_false = self._false_literal.compare(other, op, location)
        if transformed_true is NotImplemented or transformed_false is NotImplemented:
            return NotImplemented
        return ConditionalLiteralBuilder(
            true_literal=transformed_true,
            false_literal=transformed_false,
            condition=self._condition,
            location=location,
        )

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
        transformed_true = self._true_literal.binary_op(other, op, location, reverse=reverse)
        transformed_false = self._false_literal.binary_op(other, op, location, reverse=reverse)
        if transformed_true is NotImplemented or transformed_false is NotImplemented:
            return NotImplemented
        return ConditionalLiteralBuilder(
            true_literal=transformed_true,
            false_literal=transformed_false,
            condition=self._condition,
            location=location,
        )

    @typing.override
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        return super().bool_binary_op(other, op, location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        raise CodeError("cannot assign to literal", location)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        true_expr = self._true_literal.to_bytes(location)
        false_expr = self._false_literal.to_bytes(location)
        condition_expr = self._condition.resolve()
        return ConditionalExpression(
            condition=condition_expr,
            true_expr=true_expr,
            false_expr=false_expr,
            source_location=self.source_location,
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        transformed_true = self._true_literal.member_access(name, location)
        transformed_false = self._false_literal.member_access(name, location)
        return ConditionalLiteralBuilder(
            true_literal=transformed_true,
            false_literal=transformed_false,
            condition=self._condition,
            location=location,
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        true_expr = self._true_literal.bool_eval(location, negate=negate).resolve()
        false_expr = self._false_literal.bool_eval(location, negate=negate).resolve()
        condition_expr = self._condition.resolve()
        return BoolExpressionBuilder(
            ConditionalExpression(
                condition=condition_expr,
                true_expr=true_expr,
                false_expr=false_expr,
                source_location=location,
            )
        )

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        item = item.single_eval()
        transformed_true = self._true_literal.contains(item, location)
        transformed_false = self._false_literal.contains(item, location)
        return ConditionalLiteralBuilder(
            true_literal=transformed_true,
            false_literal=transformed_false,
            condition=self._condition,
            location=location,
        )

    @typing.override
    def iterate(self) -> typing.Never:
        raise CodeError("cannot iterate literal")

    @typing.override
    def iterable_item_type(self) -> typing.Never:
        self.iterate()

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        index = index.single_eval()
        transformed_true = self._true_literal.index(index, location)
        transformed_false = self._false_literal.index(index, location)
        return ConditionalLiteralBuilder(
            true_literal=transformed_true,
            false_literal=transformed_false,
            condition=self._condition,
            location=location,
        )

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
        transformed_true = self._true_literal.slice_index(
            begin_index=begin_index, end_index=end_index, stride=stride, location=location
        )
        transformed_false = self._false_literal.slice_index(
            begin_index=begin_index, end_index=end_index, stride=stride, location=location
        )
        return ConditionalLiteralBuilder(
            true_literal=transformed_true,
            false_literal=transformed_false,
            condition=self._condition,
            location=location,
        )

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        condition = self._condition.single_eval()
        return ConditionalLiteralBuilder(
            true_literal=self._true_literal,
            false_literal=self._false_literal,
            condition=condition,
            location=self.source_location,
        )


def _common_base(a: pytypes.PyType, b: pytypes.PyType, location: SourceLocation) -> pytypes.PyType:
    if a <= b:
        return a
    elif b < a:
        return b
    else:
        raise CodeError("type mismatch", location)
