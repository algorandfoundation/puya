from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    BigUIntBinaryOperator,
    BoolConstant,
    Expression,
    IntrinsicCall,
    Literal,
    UInt64BinaryOperator,
)
from puya.awst_build.eb.base import BuilderBinaryOp
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if TYPE_CHECKING:
    from puya.awst_build.eb.base import ExpressionBuilder
    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


def bool_eval_to_constant(
    *, value: bool, location: SourceLocation, negate: bool = False
) -> ExpressionBuilder:
    if negate:
        value = not value
    logger.warning(f"expression is always {value}", location=location)
    const = BoolConstant(value=value, source_location=location)
    return var_expression(const)


def uint64_to_biguint(
    arg_in: ExpressionBuilder | Expression | Literal, location: SourceLocation
) -> IntrinsicCall:
    arg = expect_operand_wtype(arg_in, wtypes.uint64_wtype)
    itob_call = IntrinsicCall(
        source_location=location,
        wtype=wtypes.biguint_wtype,
        op_code="itob",
        stack_args=[arg],
    )
    return itob_call


def translate_uint64_math_operator(
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
        raise CodeError(f"Unsupported UInt64 math operator {operator.value}", loc) from ex


def translate_biguint_math_operator(
    operator: BuilderBinaryOp, loc: SourceLocation
) -> BigUIntBinaryOperator:
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
    except ValueError as ex:
        raise CodeError(f"Unsupported BigUInt math operator {operator.value}", loc) from ex
