from __future__ import annotations

import typing

import attrs
import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    Expression,
    Not,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    Statement,
    UInt64AugmentedAssignment,
    UInt64BinaryOperation,
    UInt64BinaryOperator,
    UInt64Constant,
    UInt64UnaryOperation,
    UInt64UnaryOperator,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import (
    NotIterableInstanceExpressionBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.awst_build.utils import convert_literal_to_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class UInt64TypeBuilder(TypeBuilder, LiteralConverter):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.UInt64Type, location)

    @typing.override
    @property
    def handled_types(self) -> Collection[pytypes.PyType]:
        return (pytypes.IntLiteralType,)

    @typing.override
    def convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder:
        match literal.value:
            case int(int_value):
                expr = UInt64Constant(value=int_value, source_location=location)
                return UInt64ExpressionBuilder(expr)
        raise CodeError(f"can't covert literal {literal.value!r} to {self.produces()}", location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case []:
                const = UInt64Constant(value=0, source_location=location)
            case [LiteralBuilder(value=int(int_value))]:
                const = UInt64Constant(value=int_value, source_location=location)
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                const = UInt64Constant(value=0, source_location=location)
        return UInt64ExpressionBuilder(const)


class UInt64ExpressionBuilder(NotIterableInstanceExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.UInt64Type, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return intrinsic_factory.itob(self.resolve(), location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        as_bool = ReinterpretCast(
            expr=self.resolve(),
            wtype=wtypes.bool_wtype,
            source_location=self.resolve().source_location,
        )
        if negate:
            expr: Expression = Not(location, as_bool)
        else:
            expr = as_bool
        return BoolExpressionBuilder(expr)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        match op:
            case BuilderUnaryOp.positive:
                # unary + is allowed, but for the current types it has no real impact
                # so just expand the existing expression to include the unary operator
                return UInt64ExpressionBuilder(
                    attrs.evolve(self.resolve(), source_location=location)
                )
            case BuilderUnaryOp.bit_invert:
                return UInt64ExpressionBuilder(
                    UInt64UnaryOperation(
                        expr=self.resolve(),
                        op=UInt64UnaryOperator.bit_invert,
                        source_location=location,
                    )
                )
            case _:
                return super().unary_op(op, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        if other.pytype == self.pytype:
            pass
        else:
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.resolve(),
            operator=NumericComparison(op.value),
            rhs=other.resolve(),
        )
        return BoolExpressionBuilder(cmp_expr)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        if other.pytype == self.pytype:
            pass
        else:
            return NotImplemented
        lhs = self.resolve()
        rhs = other.resolve()
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        uint64_op = _translate_uint64_math_operator(op, location)
        bin_op_expr = UInt64BinaryOperation(
            left=lhs, op=uint64_op, right=rhs, source_location=location
        )
        return UInt64ExpressionBuilder(bin_op_expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        rhs = convert_literal_to_builder(rhs, self.pytype)
        if rhs.pytype == self.pytype:
            pass
        else:
            raise CodeError(
                f"Invalid operand type {rhs.pytype} for {op.value}= with {self.pytype}", location
            )
        target = self.resolve_lvalue()
        uint64_op = _translate_uint64_math_operator(op, location)
        return UInt64AugmentedAssignment(
            target=target, op=uint64_op, value=rhs.resolve(), source_location=location
        )


def _translate_uint64_math_operator(
    operator: BuilderBinaryOp, loc: SourceLocation
) -> UInt64BinaryOperator:
    if operator is BuilderBinaryOp.div:
        logger.error(
            (
                "To maintain semantic compatibility with Python, "
                "only the truncating division operator (//) is supported "
            ),
            location=loc,
        )
        # continue traversing code to generate any further errors
        operator = BuilderBinaryOp.floor_div
    try:
        return UInt64BinaryOperator(operator.value)
    except ValueError as ex:
        raise CodeError(f"Unsupported UInt64 math operator {operator.value!r}", loc) from ex
