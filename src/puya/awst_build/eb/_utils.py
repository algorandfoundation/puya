import structlog

from puya.awst.nodes import BoolConstant
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
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
