from __future__ import annotations

import typing

import attrs
import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    Expression,
    Literal,
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
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    NodeBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.utils import convert_literal_to_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class UInt64ClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.UInt64Type, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        match args:
            case []:
                const = UInt64Constant(value=0, source_location=location)
            case [Literal(value=int(int_value))]:
                const = UInt64Constant(value=int_value, source_location=location)
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                const = UInt64Constant(value=0, source_location=location)
        return UInt64ExpressionBuilder(const)


class UInt64ExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.UInt64Type, expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> NodeBuilder:
        as_bool = ReinterpretCast(
            expr=self.expr,
            wtype=wtypes.bool_wtype,
            source_location=self.expr.source_location,
        )
        if negate:
            expr: Expression = Not(location, as_bool)
        else:
            expr = as_bool
        return BoolExpressionBuilder(expr)

    def unary_plus(self, location: SourceLocation) -> NodeBuilder:
        # unary + is allowed, but for the current types it has no real impact
        # so just expand the existing expression to include the unary operator
        return UInt64ExpressionBuilder(attrs.evolve(self.expr, source_location=location))

    def bitwise_invert(self, location: SourceLocation) -> NodeBuilder:
        return UInt64ExpressionBuilder(
            UInt64UnaryOperation(
                expr=self.expr,
                op=UInt64UnaryOperator.bit_invert,
                source_location=location,
            )
        )

    def compare(
        self, other: NodeBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> NodeBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        if other.pytype == self.pytype:
            pass
        else:
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=NumericComparison(op.value),
            rhs=other.rvalue(),
        )
        return BoolExpressionBuilder(cmp_expr)

    def binary_op(
        self,
        other: NodeBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> NodeBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        if other.pytype == self.pytype:
            pass
        else:
            return NotImplemented
        lhs = self.expr
        rhs = other.rvalue()
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        uint64_op = _translate_uint64_math_operator(op, location)
        bin_op_expr = UInt64BinaryOperation(
            left=lhs, op=uint64_op, right=rhs, source_location=location
        )
        return UInt64ExpressionBuilder(bin_op_expr)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: NodeBuilder | Literal, location: SourceLocation
    ) -> Statement:
        rhs = convert_literal_to_builder(rhs, self.pytype)
        if rhs.pytype == self.pytype:
            pass
        else:
            raise CodeError(
                f"Invalid operand type {rhs.pytype} for {op.value}= with {self.pytype}", location
            )
        target = self.lvalue()
        uint64_op = _translate_uint64_math_operator(op, location)
        return UInt64AugmentedAssignment(
            target=target, op=uint64_op, value=rhs.rvalue(), source_location=location
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
