from __future__ import annotations

from typing import TYPE_CHECKING

from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    Literal,
    Not,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
)
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import convert_literal_to_expr

if TYPE_CHECKING:
    from immutabledict import immutabledict

    from puya.parse import SourceLocation


class ReferenceValueExpressionBuilder(ValueExpressionBuilder):
    native_wtype: wtypes.WType
    native_access_member: str
    field_mapping: immutabledict[str, tuple[str, wtypes.WType]]
    field_op_code: str
    field_bool_comment: str

    def __init__(self, expr: Expression) -> None:
        if expr.wtype == self.native_wtype:
            expr = ReinterpretCast(
                source_location=expr.source_location, wtype=self.wtype, expr=expr
            )
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        if name == self.native_access_member:
            native_cast = ReinterpretCast(
                source_location=location, wtype=self.native_wtype, expr=self.expr
            )
            return var_expression(native_cast)
        if name in self.field_mapping:
            immediate, wtype = self.field_mapping[name]
            acct_params_get = IntrinsicCall(
                source_location=location,
                wtype=wtypes.WTuple.from_types((wtype, wtypes.bool_wtype)),
                op_code=self.field_op_code,
                immediates=[immediate],
                stack_args=[self.expr],
            )
            checked_maybe = CheckedMaybe(acct_params_get, comment=self.field_bool_comment)
            return var_expression(checked_maybe)
        return super().member_access(name, location)


class UInt64BackedReferenceValueExpressionBuilder(ReferenceValueExpressionBuilder):
    native_wtype = wtypes.uint64_wtype

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
        if not (
            other_expr.wtype == self.wtype  # can only compare with other of same type?
            and op in (BuilderComparisonOp.eq, BuilderComparisonOp.ne)
        ):
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=NumericComparison(op.value),
            rhs=other_expr,
        )
        return var_expression(cmp_expr)
