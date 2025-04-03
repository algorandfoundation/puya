import typing
from collections.abc import Sequence

import attrs

from puya import algo_constants, log
from puya.awst import wtypes
from puya.awst.nodes import (
    BigUIntAugmentedAssignment,
    BigUIntBinaryOperation,
    BigUIntBinaryOperator,
    BigUIntConstant,
    Expression,
    NumericComparison,
    NumericComparisonExpression,
    Statement,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._bytes_backed import (
    BytesBackedInstanceExpressionBuilder,
    BytesBackedTypeBuilder,
)
from puyapy.awst_build.eb._utils import dummy_statement
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)

logger = log.get_logger(__name__)


class BigUIntTypeBuilder(BytesBackedTypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.BigUIntType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case int(int_value):
                pytype = self.produces()
                if int_value < 0 or int_value.bit_length() > algo_constants.MAX_BIGUINT_BITS:
                    logger.error(f"invalid {pytype} value", location=literal.source_location)
                expr = BigUIntConstant(value=int(int_value), source_location=location)
                return BigUIntExpressionBuilder(expr)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        match arg:
            case InstanceBuilder(pytype=pytypes.IntLiteralType):
                return arg.resolve_literal(converter=BigUIntTypeBuilder(location))
            case None:
                value: Expression = BigUIntConstant(value=0, source_location=location)
            case _:
                arg = expect.argument_of_type_else_dummy(arg, pytypes.UInt64Type)
                value = _uint64_to_biguint(arg, location)
        return BigUIntExpressionBuilder(value)


class BigUIntExpressionBuilder(
    NotIterableInstanceExpressionBuilder, BytesBackedInstanceExpressionBuilder
):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.BigUIntType, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        cmp_expr = NumericComparisonExpression(
            lhs=self.resolve(),
            operator=NumericComparison.eq if negate else NumericComparison.ne,
            rhs=BigUIntConstant(value=0, source_location=location),
            source_location=location,
        )
        return BoolExpressionBuilder(cmp_expr)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        if op == BuilderUnaryOp.positive:
            # unary + is allowed, but for the current types it has no real impact
            # so just expand the existing expression to include the unary operator
            return BigUIntExpressionBuilder(attrs.evolve(self.resolve(), source_location=location))
        return super().unary_op(op, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.resolve_literal(converter=BigUIntTypeBuilder(other.source_location))
        if pytypes.BigUIntType <= other.pytype:
            other_expr = other.resolve()
        elif pytypes.UInt64Type <= other.pytype:
            other_expr = _uint64_to_biguint(other, location)
        else:
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.resolve(),
            operator=NumericComparison(op.value),
            rhs=other_expr,
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
        biguint_op = _translate_biguint_math_operator(op, location)
        if biguint_op is None:
            return NotImplemented
        other = other.resolve_literal(converter=BigUIntTypeBuilder(other.source_location))
        if pytypes.BigUIntType <= other.pytype:
            other_expr = other.resolve()
        elif pytypes.UInt64Type <= other.pytype:
            other_expr = _uint64_to_biguint(other, location)
        else:
            return NotImplemented
        lhs = self.resolve()
        rhs = other_expr
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        bin_op_expr = BigUIntBinaryOperation(
            source_location=location, left=lhs, op=biguint_op, right=rhs
        )
        return BigUIntExpressionBuilder(bin_op_expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        biguint_op = _translate_biguint_math_operator(op, location)
        if biguint_op is None:
            logger.error(f"unsupported operator for type: {op.value!r}", location=location)
            return dummy_statement(location)
        if pytypes.UInt64Type <= rhs.pytype:
            value = _uint64_to_biguint(rhs, location)
        else:
            value = expect.argument_of_type_else_dummy(
                rhs, self.pytype, resolve_literal=True
            ).resolve()
        target = self.resolve_lvalue()
        return BigUIntAugmentedAssignment(
            source_location=location,
            target=target,
            value=value,
            op=biguint_op,
        )


def _translate_biguint_math_operator(
    operator: BuilderBinaryOp, loc: SourceLocation
) -> BigUIntBinaryOperator | None:
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
        return BigUIntBinaryOperator(operator.value)
    except ValueError:
        return None


def _uint64_to_biguint(arg_in: InstanceBuilder, location: SourceLocation) -> Expression:
    return intrinsic_factory.itob_as(arg_in.resolve(), wtypes.biguint_wtype, location)
