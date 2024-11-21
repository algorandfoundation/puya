from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesComparisonExpression,
    EqualityComparison,
    Expression,
    ExpressionStatement,
    ReinterpretCast,
    Statement,
    VarExpression,
)
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
)

logger = log.get_logger(__name__)


def dummy_value(pytype: pytypes.PyType, location: SourceLocation) -> InstanceBuilder:
    if isinstance(pytype, pytypes.LiteralOnlyType):
        from puyapy.awst_build.eb._literals import LiteralBuilderImpl

        return LiteralBuilderImpl(pytype.python_type(), location)
    expr = VarExpression(name="", wtype=pytype.checked_wtype(location), source_location=location)
    return builder_for_instance(pytype, expr)


def dummy_statement(location: SourceLocation) -> Statement:
    return ExpressionStatement(
        VarExpression(
            name="",
            wtype=wtypes.void_wtype,
            source_location=location,
        )
    )


def resolve_negative_literal_index(
    index: InstanceBuilder, length: InstanceBuilder, location: SourceLocation
) -> InstanceBuilder:
    match index:
        case LiteralBuilder(value=int(int_index)) if int_index < 0:
            return length.binary_op(
                index.unary_op(BuilderUnaryOp.negative, location),
                BuilderBinaryOp.sub,
                location,
                reverse=False,
            )
        case _:
            from puyapy.awst_build.eb.uint64 import UInt64TypeBuilder

            return index.resolve_literal(UInt64TypeBuilder(index.source_location))


def constant_bool_and_error(
    *, value: bool, location: SourceLocation, negate: bool = False
) -> InstanceBuilder:
    """
    Returns a constant bool instance builder for the specified value and negate combination.

    Always emits an error as either allowing the expression would result in a semantic
    compatability issue, or indicates the user has most likely made a mistake
    """
    from puyapy.awst_build.eb._literals import LiteralBuilderImpl

    if negate:
        value = not value
    logger.error(f"expression is always {value}", location=location)
    return LiteralBuilderImpl(value=value, source_location=location)


def compare_bytes(
    *,
    self: InstanceBuilder,
    op: BuilderComparisonOp,
    other: InstanceBuilder,
    source_location: SourceLocation,
) -> InstanceBuilder:
    # defer to most derived type if not equal
    if not (other.pytype <= self.pytype):
        return NotImplemented
    return _compare_expr_bytes_unchecked(self.resolve(), op, other.resolve(), source_location)


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
    from puyapy.awst_build.eb.bool import BoolExpressionBuilder

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
