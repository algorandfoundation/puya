import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.avm import AVMType
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesComparisonExpression,
    BytesConstant,
    BytesEncoding,
    Copy,
    EqualityComparison,
    Expression,
    ExpressionStatement,
    ReinterpretCast,
    Statement,
    StringConstant,
    VarExpression,
    can_reinterpret_cast,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
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
    compatibility issue, or indicates the user has most likely made a mistake
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
        return NotImplemented  # type: ignore[no-any-return]
    return _compare_expr_bytes_unchecked(self.resolve(), op, other.resolve(), source_location)


def compare_expr_bytes(
    *,
    lhs: Expression,
    op: BuilderComparisonOp,
    rhs: Expression,
    source_location: SourceLocation,
) -> InstanceBuilder:
    if rhs.wtype != lhs.wtype:
        return NotImplemented  # type: ignore[no-any-return]
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
        return NotImplemented  # type: ignore[no-any-return]
    cmp_expr = BytesComparisonExpression(
        lhs=lhs,
        operator=eq_op,
        rhs=rhs,
        source_location=location,
    )
    return BoolExpressionBuilder(cmp_expr)


def cast_to_bytes(expr: Expression, location: SourceLocation | None = None) -> Expression:
    return reinterpret_cast(
        expr=expr, wtype=wtypes.bytes_wtype, source_location=location or expr.source_location
    )


def upcast_bool_to_uint64(
    builder: InstanceBuilder, location: SourceLocation | None = None
) -> InstanceBuilder:
    from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

    assert builder.pytype == pytypes.BoolType
    expr = reinterpret_cast(
        expr=builder.resolve(),
        wtype=wtypes.uint64_wtype,
        source_location=location or builder.source_location,
    )
    return UInt64ExpressionBuilder(expr)


class CopyBuilder(FunctionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation, typ: pytypes.PyType):
        super().__init__(location)
        self._typ = typ
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        expr_result = Copy(value=self.expr, source_location=location)
        return builder_for_instance(self._typ, expr_result)


def reinterpret_cast(
    expr: Expression,
    wtype: wtypes.WType,
    *,
    source_location: SourceLocation | None = None,
) -> Expression:
    loc = source_location or expr.source_location
    if expr.wtype == wtype:
        return expr
    if isinstance(expr, ReinterpretCast):
        # if the cast is a round-trip, we can eliminate it - unless it's
        # an aggregate type, which might have copy semantics to worry about
        if expr.expr.wtype == wtype and not wtype.is_aggregate:
            return expr.expr
        # otherwise, see if we can reduce from two casts to just one
        # without triggering a validation error
        if can_reinterpret_cast(source_wtype=expr.expr.wtype, target_wtype=wtype):
            return attrs.evolve(expr, wtype=wtype, source_location=loc)
    elif wtype.scalar_type == AVMType.bytes:
        # if the source is a bytes-like constant, re-emit it directly as a
        # BytesConstant of the target wtype rather than wrapping in a
        # ReinterpretCast - except when the target imposes a fixed length that
        # the constant doesn't satisfy, since that'd produce an invalid constant
        match _extract_bytes_constant(expr):
            case bytes(encoded), BytesEncoding() as encoding if (
                not _invalid_constant_length(encoded, wtype)
            ):
                return BytesConstant(
                    value=encoded, wtype=wtype, encoding=encoding, source_location=loc
                )
    return ReinterpretCast(expr=expr, wtype=wtype, source_location=loc)


def _extract_bytes_constant(expr: Expression) -> tuple[bytes, BytesEncoding] | None:
    match expr:
        case BytesConstant(value=encoded, encoding=encoding):
            return encoded, encoding
        case StringConstant(wtype=wtypes.string_wtype):
            encoded = expr.value.encode("utf8")
            return encoded, BytesEncoding.utf8
        case _:
            return None


def _invalid_constant_length(value: bytes, wtype: wtypes.WType) -> bool:
    return (
        isinstance(wtype, wtypes.BytesWType)
        and wtype.length is not None
        and wtype.length != len(value)
    )
