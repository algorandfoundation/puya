from __future__ import annotations

import typing

from wyvern.awst import wtypes
from wyvern.awst.nodes import (
    Expression,
    Literal,
    Not,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    UInt64Constant,
)
from wyvern.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.awst_build.utils import convert_literal_to_expr, expect_operand_wtype
from wyvern.errors import CodeError

if typing.TYPE_CHECKING:
    import mypy.nodes

    from wyvern.parse import SourceLocation


def as_wtype(expr: Expression, loc: SourceLocation, wtype: wtypes.WType) -> Expression:
    if expr.wtype == wtype:
        return expr
    return ReinterpretCast(source_location=loc, wtype=wtype, expr=expr)


def as_uint64(expr: Expression, loc: SourceLocation) -> Expression:
    return as_wtype(expr, loc, wtypes.uint64_wtype)


def as_asset(expr: Expression, loc: SourceLocation) -> Expression:
    return as_wtype(expr, loc, wtypes.asset_wtype)


class AssetClassExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.asset_wtype

    def call(
        self,
        args: typing.Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb]:
                uint64_expr = expect_operand_wtype(eb, wtypes.uint64_wtype)
                return AssetExpressionBuilder(uint64_expr)
            case [Literal(value=int(int_value), source_location=loc)]:
                const = UInt64Constant(value=int_value, source_location=loc)
                return AssetExpressionBuilder(const)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class AssetExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.asset_wtype

    def __init__(self, expr: Expression) -> None:
        super().__init__(as_asset(expr, expr.source_location))

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "asset_id":
                return var_expression(as_uint64(self.expr, location))
            case _:
                return super().member_access(name, location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        as_bool = ReinterpretCast(
            expr=self.expr,
            wtype=wtypes.bool_wtype,
            source_location=self.expr.source_location,
        )
        if negate:
            expr: Expression = Not(location, as_bool)
        else:
            expr = as_bool
        return var_expression(expr)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        if other_expr.wtype != self.wtype:  # can only compare with other assets?
            return NotImplemented
        match op:
            case BuilderComparisonOp.eq | BuilderComparisonOp.ne:
                pass
            case _:
                return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=as_uint64(self.expr, location),
            operator=NumericComparison(op.value),
            rhs=as_uint64(other_expr, location),
        )
        return var_expression(cmp_expr)
