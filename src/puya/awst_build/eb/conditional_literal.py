import typing

from puya.awst.nodes import ConditionalExpression, Expression, Lvalue, Statement
from puya.awst_build import pytypes
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    Iteration,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.errors import CodeError
from puya.parse import SourceLocation


class ConditionalLiteralBuilder(InstanceBuilder):
    def __init__(
        self,
        *,
        true_literal: LiteralBuilder,
        false_literal: LiteralBuilder,
        condition: Expression,
        location: SourceLocation
    ):
        super().__init__(location)
        assert true_literal.pytype == false_literal.pytype  # TODO: fixme
        self._pytype = true_literal.pytype
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
        return ConditionalExpression(
            condition=self._condition,
            true_expr=true_expr,
            false_expr=false_expr,
            source_location=self.source_location,
        )

    @typing.override
    def resolve_literal(self, converter: LiteralConverter) -> InstanceBuilder:
        true_b = converter.convert_literal(
            literal=self._true_literal, location=converter.source_location
        )
        false_b = converter.convert_literal(
            literal=self._false_literal, location=converter.source_location
        )
        assert true_b.pytype == false_b.pytype  # TODO: fixme
        result_pytype = true_b.pytype
        true_expr = true_b.resolve()
        false_expr = false_b.resolve()
        result_expr = ConditionalExpression(
            condition=self._condition,
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
        transformed_true = self._true_literal.compare(other, op, location)
        transformed_false = self._false_literal.compare(other, op, location)
        if transformed_true is NotImplemented:
            assert transformed_false is NotImplemented  # TODO: fixme
            return NotImplemented
        if isinstance(transformed_true, LiteralBuilder):
            assert isinstance(transformed_false, LiteralBuilder)  # TODO: fixme
            return ConditionalLiteralBuilder(
                true_literal=transformed_true,
                false_literal=transformed_false,
                condition=self._condition,
                location=location,
            )
        true_expr = transformed_true.resolve()
        false_expr = transformed_false.resolve()
        result_expr = ConditionalExpression(
            condition=self._condition,
            true_expr=true_expr,
            false_expr=false_expr,
            source_location=location,
        )
        return BoolExpressionBuilder(result_expr)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool
    ) -> InstanceBuilder:
        transformed_true = self._true_literal.binary_op(other, op, location, reverse=reverse)
        transformed_false = self._false_literal.binary_op(other, op, location, reverse=reverse)
        if transformed_true is NotImplemented:
            assert transformed_false is NotImplemented  # TODO: fixme
            return NotImplemented
        assert transformed_true.pytype == transformed_false.pytype  # TODO: fixme
        result_pytype = transformed_true.pytype
        if isinstance(transformed_true, LiteralBuilder):
            assert isinstance(transformed_false, LiteralBuilder)  # TODO: fixme
            return ConditionalLiteralBuilder(
                true_literal=transformed_true,
                false_literal=transformed_false,
                condition=self._condition,
                location=location,
            )
        true_expr = transformed_true.resolve()  # TODO: maybe we pass other to resolve..?
        false_expr = transformed_false.resolve()
        result_expr = ConditionalExpression(
            condition=self._condition,
            true_expr=true_expr,
            false_expr=false_expr,
            source_location=location,
        )
        return builder_for_instance(result_pytype, result_expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        raise CodeError("cannot assign to literal", location)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        true_expr = self._true_literal.to_bytes(location)
        false_expr = self._false_literal.to_bytes(location)
        return ConditionalExpression(
            condition=self._condition,
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
        return BoolExpressionBuilder(
            ConditionalExpression(
                condition=self._condition,
                true_expr=true_expr,
                false_expr=false_expr,
                source_location=location,
            )
        )

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        raise NotImplementedError("TODO")

    @typing.override
    def iterate(self) -> Iteration:
        raise NotImplementedError("TODO")

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        raise NotImplementedError("TODO")

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise NotImplementedError("TODO")
