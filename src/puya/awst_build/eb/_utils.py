from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import BoolConstant, Expression, Literal
from puya.awst_build import intrinsic_factory
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype

if typing.TYPE_CHECKING:
    from puya.awst_build.eb.base import ExpressionBuilder
    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


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
) -> Expression:
    arg = expect_operand_wtype(arg_in, wtypes.uint64_wtype)

    return intrinsic_factory.itob_as(
        arg,
        wtypes.biguint_wtype,
        location,
    )
