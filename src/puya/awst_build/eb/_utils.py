from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import BoolConstant, Expression, Literal, ReinterpretCast
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb.base import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.utils import expect_operand_type

if typing.TYPE_CHECKING:
    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def bool_eval_to_constant(
    *, value: bool, location: SourceLocation, negate: bool = False
) -> InstanceBuilder:
    if negate:
        value = not value
    logger.warning(f"expression is always {value}", location=location)
    const = BoolConstant(value=value, source_location=location)
    return BoolExpressionBuilder(const)


def uint64_to_biguint(arg_in: NodeBuilder | Literal, location: SourceLocation) -> Expression:
    arg = expect_operand_type(arg_in, pytypes.UInt64Type).rvalue()

    return intrinsic_factory.itob_as(
        arg,
        wtypes.biguint_wtype,
        location,
    )


def get_bytes_expr(expr: Expression) -> ReinterpretCast:
    return ReinterpretCast(
        expr=expr, wtype=wtypes.bytes_wtype, source_location=expr.source_location
    )


def get_bytes_expr_builder(expr: Expression) -> InstanceBuilder:
    return BytesExpressionBuilder(get_bytes_expr(expr))
