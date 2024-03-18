from __future__ import annotations

import typing

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    BytesAugmentedAssignment,
    BytesBinaryOperation,
    BytesBinaryOperator,
    BytesComparisonExpression,
    CallArg,
    EqualityComparison,
    Expression,
    FreeSubroutineTarget,
    Literal,
    ReinterpretCast,
    Statement,
    StringConstant,
    SubroutineCallExpression,
)
from puya.awst_build import intrinsic_factory
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class StringClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.string_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                value = ""
            case [Literal(value=str(value))]:
                pass
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        str_const = StringConstant(value=value, source_location=location)
        return var_expression(str_const)


class StringExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.string_wtype

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        match name:
            case "bytes":
                return _get_bytes_expr_builder(self.expr)
            case _:
                raise CodeError(f"Unrecognised member of {self.wtype}: {name}", location)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        match op:
            case BuilderBinaryOp.add:
                return BytesAugmentedAssignment(
                    target=self.lvalue(),
                    op=BytesBinaryOperator.add,
                    value=expect_operand_wtype(rhs, self.wtype),
                    source_location=location,
                )
            case _:
                raise CodeError(
                    f"Unsupported augmented assignment operation on {self.wtype}: {op.value}=",
                    location,
                )

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
                rhs = expect_operand_wtype(other, self.wtype)
                if reverse:
                    (lhs, rhs) = (rhs, lhs)
                return var_expression(
                    BytesBinaryOperation(
                        left=lhs,
                        op=BytesBinaryOperator.add,
                        right=rhs,
                        source_location=location,
                    )
                )
            case _:
                return NotImplemented

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = expect_operand_wtype(other, self.wtype)

        cmp = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison(op.value),
            rhs=other_expr,
        )
        return var_expression(cmp)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        bytes_expr = _get_bytes_expr(self.expr)
        len_expr = intrinsic_factory.bytes_len(bytes_expr, location)
        len_builder = var_expression(len_expr)
        return len_builder.bool_eval(location, negate=negate)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        item_expr = _get_bytes_expr(expect_operand_wtype(item, wtypes.string_wtype))
        this_expr = _get_bytes_expr(self.expr)
        is_substring_expr = SubroutineCallExpression(
            target=FreeSubroutineTarget(module_name="puyapy_lib_bytes", name="is_substring"),
            args=[
                CallArg(value=item_expr, name="item"),
                CallArg(value=this_expr, name="sequence"),
            ],
            wtype=wtypes.bool_wtype,
            source_location=location,
        )
        return var_expression(is_substring_expr)


def _get_bytes_expr(expr: Expression) -> ReinterpretCast:
    return ReinterpretCast(
        expr=expr, wtype=wtypes.bytes_wtype, source_location=expr.source_location
    )


def _get_bytes_expr_builder(expr: Expression) -> ExpressionBuilder:
    return var_expression(_get_bytes_expr(expr))
