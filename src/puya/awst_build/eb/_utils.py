from collections.abc import Sequence
from itertools import zip_longest

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
from puya.awst_build import pytypes
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puya.awst_build.eb.uint64 import UInt64TypeBuilder
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def dummy_value(pytype: pytypes.PyType, location: SourceLocation) -> InstanceBuilder:
    expr = VarExpression(name="", wtype=pytype.wtype, source_location=location)
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
            return index.resolve_literal(UInt64TypeBuilder(index.source_location))


def bool_eval_to_constant(
    *, value: bool, location: SourceLocation, negate: bool = False
) -> InstanceBuilder:
    # TODO(frist)(frist): this function hides multiple semantic compatibility issues,
    #       it's used frequently without retaining the underlying expression,
    #       so it's never evaluated, which is wrong if there are side effects
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


def expect_at_most_one_arg(
    args: Sequence[NodeBuilder], location: SourceLocation
) -> InstanceBuilder | None:
    if not args:
        return None
    eb, *extra = map(require_instance_builder, args)
    if extra:
        logger.error(f"expected at most 1 argument, got {len(args)}", location=location)
    return eb


def expect_at_least_one_arg(
    args: Sequence[NodeBuilder], location: SourceLocation
) -> tuple[InstanceBuilder, Sequence[InstanceBuilder]]:
    if not args:
        raise CodeError("expected at least 1 argument, got 0", location)
    first, *rest = map(require_instance_builder, args)
    return first, rest


def expect_exactly_one_arg(
    args: Sequence[NodeBuilder], location: SourceLocation
) -> InstanceBuilder:
    if not args:
        raise CodeError("expected 1 argument, got 0", location)
    eb, *extra = map(require_instance_builder, args)
    if extra:
        logger.error(f"expected 1 argument, got {len(args)}", location=location)
    return eb


def expect_exactly_one_arg_of_type(
    args: Sequence[NodeBuilder], pytype: pytypes.PyType, location: SourceLocation
) -> InstanceBuilder:
    if not args:
        logger.error("expected 1 argument, got 0", location=location)
        return dummy_value(pytype, location)
    first, *rest = args
    if rest:
        logger.error(f"expected 1 argument, got {len(args)}", location=location)
    if isinstance(first, InstanceBuilder) and first.pytype == pytype:
        return first
    logger.error("unexpected argument type", location=first.source_location)
    return dummy_value(pytype, first.source_location)


def expect_no_args(args: Sequence[NodeBuilder], location: SourceLocation) -> None:
    if args:
        logger.error(f"expected 0 arguments, got {len(args)}", location)


def expect_exactly_n_args_of_type(
    args: Sequence[NodeBuilder], pytype: pytypes.PyType, location: SourceLocation, num_args: int
) -> Sequence[InstanceBuilder]:
    if len(args) != num_args:
        logger.error(
            f"expected {num_args} argument{'' if num_args == 1 else 's'}, got {len(args)}",
            location=location,
        )
        dummy_args = [dummy_value(pytype, location)] * num_args
        args = [arg or default for arg, default in zip_longest(args, dummy_args)]
    arg_ebs = [expect_argument_of_type(arg, pytype) for arg in args]
    return arg_ebs[:num_args]


def expect_argument_of_type(builder: NodeBuilder, target_type: pytypes.PyType) -> InstanceBuilder:
    if isinstance(builder, InstanceBuilder) and builder.pytype == target_type:
        return builder
    logger.error("unexpected argument type", location=builder.source_location)
    return dummy_value(target_type, builder.source_location)
