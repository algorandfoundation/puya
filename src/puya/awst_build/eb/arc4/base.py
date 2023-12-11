from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    BytesComparisonExpression,
    EqualityComparison,
    Expression,
    Literal,
    ReinterpretCast,
)
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError, InternalError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


def arc4_to_avm_wtype(arc4_wtype: wtypes.WType) -> wtypes.WType:
    match arc4_wtype:
        case wtypes.arc4_string_wtype:
            return wtypes.bytes_wtype
        case wtypes.arc4_bool_wtype:
            return wtypes.bool_wtype
        case wtypes.ARC4UIntN(n=n) | wtypes.ARC4UFixedNxM(n=n):
            return wtypes.uint64_wtype if n <= 64 else wtypes.biguint_wtype
        case wtypes.ARC4Tuple(types=types):
            return wtypes.WTuple.from_types(types)
    raise InternalError("Invalid arc4_wtype")


def get_bytes_expr(expr: Expression) -> ReinterpretCast:
    return ReinterpretCast(
        expr=expr, wtype=wtypes.bytes_wtype, source_location=expr.source_location
    )


def get_bytes_expr_builder(expr: Expression) -> ExpressionBuilder:
    return var_expression(get_bytes_expr(expr))


class ARC4ClassExpressionBuilder(BytesBackedClassExpressionBuilder, ABC):
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        match name:
            case "encode":
                return ARC4EncodeBuilder(location, self.produces())
            case _:
                return super().member_access(name, location)


def get_integer_literal_value(eb_or_literal: ExpressionBuilder | Literal, purpose: str) -> int:
    match eb_or_literal:
        case Literal(value=int(lit_value)):
            return lit_value
        case _:
            raise CodeError(f"{purpose} must be compile time constant")


class ARC4EncodeBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.WType):
        super().__init__(location=location)
        self.wtype = wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb] if eb.rvalue().wtype == arc4_to_avm_wtype(self.wtype):
                value = eb.rvalue()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)

        return var_expression(
            ARC4Encode(
                source_location=location,
                value=value,
                wtype=self.wtype,
            )
        )


class ARC4DecodeBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation):
        super().__init__(location=location)
        match expr.wtype:
            case wtypes.arc4_string_wtype:
                pass
            case wtypes.ARC4UIntN():
                pass
            case wtypes.ARC4UFixedNxM():
                pass
            case wtypes.arc4_bool_wtype:
                pass
            case wtypes.ARC4Tuple():
                pass
            case _:
                raise InternalError("Unsupported wtype")
        self.expr = expr

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case []:
                pass
            case _:
                raise CodeError("Invalid/unhandled arguments", location)

        expr = ARC4Decode(
            source_location=location, value=self.expr, wtype=arc4_to_avm_wtype(self.expr.wtype)
        )
        return var_expression(expr)


class ARC4EncodedExpressionBuilder(ValueExpressionBuilder):
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        match name:
            case "decode":
                return ARC4DecodeBuilder(self.expr, location)
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                raise CodeError(f"Unrecognised member of bytes: {name}", location)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        if isinstance(other, Literal):
            raise CodeError(
                f"Cannot compare arc4 encoded value of {self.wtype} to a literal value", location
            )
        other_expr = other.rvalue()
        if other_expr.wtype != self.wtype:
            return NotImplemented
        cmp_expr = BytesComparisonExpression(
            source_location=location,
            lhs=get_bytes_expr(self.expr),
            operator=EqualityComparison(op.value),
            rhs=get_bytes_expr(other_expr),
        )
        return var_expression(cmp_expr)
