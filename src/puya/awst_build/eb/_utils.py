from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesComparisonExpression,
    EqualityComparison,
    Expression,
    ReinterpretCast,
)
from puya.awst_build.eb.interface import BuilderComparisonOp, InstanceBuilder

if typing.TYPE_CHECKING:
    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def bool_eval_to_constant(
    *, value: bool, location: SourceLocation, negate: bool = False
) -> InstanceBuilder:
    from puya.awst_build.eb._literals import LiteralBuilderImpl

    if negate:
        value = not value
    logger.warning(f"expression is always {value}", location=location)
    return LiteralBuilderImpl(value=value, source_location=location)


def compare_bytes(
    *,
    lhs: InstanceBuilder,
    op: BuilderComparisonOp,
    rhs: InstanceBuilder,
    source_location: SourceLocation,
) -> InstanceBuilder:
    if rhs.pytype != lhs.pytype:
        return NotImplemented
    return _compare_expr_bytes_unchecked(lhs.resolve(), op, rhs.resolve(), source_location)


def compare_expr_bytes(
    *,
    lhs: Expression,
    op: BuilderComparisonOp,
    rhs: Expression,
    source_location: SourceLocation,
) -> InstanceBuilder:
    if rhs.wtype != lhs.wtype:
        return NotImplemented
    return _compare_expr_bytes_unchecked(lhs, op, rhs, source_location)


def _compare_expr_bytes_unchecked(
    lhs: Expression,
    op: BuilderComparisonOp,
    rhs: Expression,
    location: SourceLocation,
) -> InstanceBuilder:
    from puya.awst_build.eb.bool import BoolExpressionBuilder

    try:
        eq_op = EqualityComparison(op.value)
    except ValueError:
        return NotImplemented
    cmp_expr = BytesComparisonExpression(
        lhs=lhs,
        operator=eq_op,
        rhs=rhs,
        source_location=location,
    )
    return BoolExpressionBuilder(cmp_expr)


def cast_to_bytes(expr: Expression, location: SourceLocation | None = None) -> ReinterpretCast:
    return ReinterpretCast(
        expr=expr, wtype=wtypes.bytes_wtype, source_location=location or expr.source_location
    )
