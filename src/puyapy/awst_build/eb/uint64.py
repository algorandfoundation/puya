import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    Expression,
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
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._utils import dummy_statement
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)

logger = log.get_logger(__name__)


class UInt64TypeBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.UInt64Type, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case int(int_value):
                pytype = self.produces()
                if int_value < 0 or int_value.bit_length() > 64:
                    logger.error(f"invalid {pytype} value", location=literal.source_location)
                # take int() of the value since it could match a bool also
                expr = UInt64Constant(value=int(int_value), source_location=location)
                return UInt64ExpressionBuilder(expr)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg_of_type(
            args, [pytypes.IntLiteralType, pytypes.BoolType], location
        )
        match arg:
            case InstanceBuilder(pytype=pytypes.IntLiteralType):
                return arg.resolve_literal(converter=UInt64TypeBuilder(location))
            case InstanceBuilder(pytype=pytypes.BoolType):
                return _upcast_bool(arg, location)
            case _:
                return UInt64ExpressionBuilder(UInt64Constant(value=0, source_location=location))


class UInt64ExpressionBuilder(NotIterableInstanceExpressionBuilder):
    def __init__(self, expr: Expression, enum_type: pytypes.UInt64EnumType | None = None):
        if enum_type is None:
            pytype = pytypes.UInt64Type
        else:
            pytype = enum_type
        super().__init__(pytype, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return intrinsic_factory.itob(self.resolve(), location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        cmp_expr = NumericComparisonExpression(
            lhs=self.resolve(),
            operator=NumericComparison.eq if negate else NumericComparison.ne,
            rhs=UInt64Constant(value=0, source_location=location),
            source_location=location,
        )
        return BoolExpressionBuilder(cmp_expr)

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
        other = _resolve_literal_and_upcast_bool(other)
        if not (pytypes.UInt64Type <= other.pytype):
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
        uint64_op = _translate_uint64_math_operator(op, location)
        if uint64_op is None:
            return NotImplemented
        other = _resolve_literal_and_upcast_bool(other)
        if not (pytypes.UInt64Type <= other.pytype):
            return NotImplemented

        lhs = self.resolve()
        rhs = other.resolve()
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        bin_op_expr = UInt64BinaryOperation(
            left=lhs, op=uint64_op, right=rhs, source_location=location
        )
        return UInt64ExpressionBuilder(bin_op_expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        uint64_op = _translate_uint64_math_operator(op, location)
        if uint64_op is None:
            logger.error(f"unsupported operator for type: {op.value!r}", location=location)
            return dummy_statement(location)
        rhs = _resolve_literal_and_upcast_bool(rhs)
        # note: don't check for enum types here, mypy errors anyway
        rhs = expect.argument_of_type_else_dummy(rhs, pytypes.UInt64Type)
        target = self.resolve_lvalue()
        return UInt64AugmentedAssignment(
            target=target, op=uint64_op, value=rhs.resolve(), source_location=location
        )


def _translate_uint64_math_operator(
    operator: BuilderBinaryOp, loc: SourceLocation
) -> UInt64BinaryOperator | None:
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
    except ValueError:
        return None


def _resolve_literal_and_upcast_bool(other: InstanceBuilder) -> InstanceBuilder:
    other = other.resolve_literal(converter=UInt64TypeBuilder(other.source_location))
    if other.pytype == pytypes.BoolType:
        return _upcast_bool(other)
    return other


def _upcast_bool(
    builder: InstanceBuilder, location: SourceLocation | None = None
) -> InstanceBuilder:
    assert builder.pytype == pytypes.BoolType
    expr = ReinterpretCast(
        expr=builder.resolve(),
        wtype=wtypes.uint64_wtype,
        source_location=location or builder.source_location,
    )
    return UInt64ExpressionBuilder(expr)
