from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    ArrayConcat,
    ArrayExtend,
    BytesComparisonExpression,
    BytesConstant,
    BytesEncoding,
    EqualityComparison,
    Expression,
    ExpressionStatement,
    Literal,
    Statement,
)
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    ARC4EncodedExpressionBuilder,
    get_bytes_expr,
)
from puya.awst_build.eb.base import BuilderBinaryOp, BuilderComparisonOp, ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class StringClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.arc4_string_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=str(str_val), source_location=loc)]:
                return var_expression(
                    ARC4Encode(
                        value=BytesConstant(
                            value=str_val.encode("utf8"),
                            source_location=loc,
                            encoding=BytesEncoding.utf8,
                        ),
                        source_location=location,
                        wtype=self.produces(),
                    )
                )
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


def arc4_encode_bytes(bytes_expr: Expression, source_location: SourceLocation) -> Expression:
    return ARC4Encode(
        value=bytes_expr, source_location=source_location, wtype=wtypes.arc4_string_wtype
    )


def expect_string_or_bytes(expr: ExpressionBuilder | Literal) -> Expression:
    match expr:
        case Literal(value=str(string_literal), source_location=source_location):
            return arc4_encode_bytes(
                BytesConstant(
                    value=string_literal.encode("utf-8"),
                    encoding=BytesEncoding.utf8,
                    source_location=source_location,
                ),
                source_location,
            )
        case Literal(value=bytes(bytes_literal), source_location=source_location):
            return arc4_encode_bytes(
                BytesConstant(
                    value=bytes_literal,
                    encoding=BytesEncoding.utf8,
                    source_location=source_location,
                ),
                source_location,
            )
        case ExpressionBuilder() as eb:
            rvalue = eb.rvalue()
            if rvalue.wtype == wtypes.arc4_string_wtype:
                return rvalue
            if rvalue.wtype == wtypes.bytes_wtype:
                return arc4_encode_bytes(rvalue, eb.source_location)
    raise CodeError("Expected String or Bytes, or a str or bytes literal", expr.source_location)


class StringExpressionBuilder(ARC4EncodedExpressionBuilder):
    wtype = wtypes.arc4_string_wtype

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        match op:
            case BuilderBinaryOp.add:
                return ExpressionStatement(
                    expr=ArrayExtend(
                        base=self.expr,
                        other=expect_string_or_bytes(rhs),
                        source_location=location,
                        wtype=wtypes.arc4_string_wtype,
                    )
                )
            case _:
                return super().augmented_assignment(op, rhs, location)

    def binary_op(
        self,
        other: ExpressionBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> ExpressionBuilder:
        match op:
            case BuilderBinaryOp.add:
                lhs = self.expr
                rhs = expect_string_or_bytes(other)
                if reverse:
                    (lhs, rhs) = (rhs, lhs)
                return var_expression(
                    ArrayConcat(
                        left=lhs,
                        right=rhs,
                        source_location=location,
                        wtype=wtypes.arc4_string_wtype,
                    )
                )

            case _:
                return super().binary_op(other, op, location, reverse=reverse)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr: Expression
        match other:
            case Literal(value=str(string_literal), source_location=source_location):
                other_expr = arc4_encode_bytes(
                    BytesConstant(
                        value=string_literal.encode("utf-8"),
                        encoding=BytesEncoding.utf8,
                        source_location=source_location,
                    ),
                    source_location,
                )
            case ExpressionBuilder() as eb if eb.rvalue().wtype == wtypes.arc4_string_wtype:
                other_expr = eb.rvalue()
            case _:
                raise CodeError("Expected arc4.String or str literal")

        return var_expression(
            BytesComparisonExpression(
                source_location=location,
                lhs=get_bytes_expr(self.expr),
                operator=EqualityComparison(op.value),
                rhs=get_bytes_expr(other_expr),
            )
        )
