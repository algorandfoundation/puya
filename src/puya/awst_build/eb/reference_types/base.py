from __future__ import annotations

import typing

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
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.utils import convert_literal_to_expr

if typing.TYPE_CHECKING:
    from immutabledict import immutabledict

    from puya.parse import SourceLocation


class ReferenceValueExpressionBuilder(ValueExpressionBuilder):
    native_type: pytypes.PyType
    native_access_member: str
    field_mapping: immutabledict[str, tuple[str, pytypes.PyType]]
    field_op_code: str
    field_bool_comment: str

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        if name == self.native_access_member:
            native_cast = ReinterpretCast(
                expr=self.expr, wtype=self.native_type.wtype, source_location=location
            )
            return builder_for_instance(self.native_type, native_cast)
        if name in self.field_mapping:
            immediate, typ = self.field_mapping[name]
            acct_params_get = IntrinsicCall(
                source_location=location,
                wtype=wtypes.WTuple((typ.wtype, wtypes.bool_wtype), location),
                op_code=self.field_op_code,
                immediates=[immediate],
                stack_args=[self.expr],
            )
            checked_maybe = CheckedMaybe(acct_params_get, comment=self.field_bool_comment)
            return builder_for_instance(typ, checked_maybe)
        return super().member_access(name, location)


class UInt64BackedReferenceValueExpressionBuilder(ReferenceValueExpressionBuilder):
    native_type = pytypes.UInt64Type

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
        return BoolExpressionBuilder(expr)

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
        return BoolExpressionBuilder(cmp_expr)
