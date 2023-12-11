from puya.awst.nodes import (
    Expression,
    Literal,
    Lvalue,
    Statement,
)
from puya.awst_build.eb.base import BuilderComparisonOp, ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import create_temporary_assignment
from puya.errors import InternalError
from puya.parse import SourceLocation


class TemporaryAssignmentExpressionBuilder(ExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(expr.source_location)
        assign_expr = create_temporary_assignment(expr)
        self.target = assign_expr.read
        self.assignment = assign_expr.define
        self.is_first_access = True

    def lvalue(self) -> Lvalue:
        raise InternalError(
            "Temporary assignment should not be used as an assignment target itself"
        )

    def rvalue(self) -> Expression:
        if self.is_first_access:
            self.is_first_access = False
            return self.assignment
        return self.target

    def delete(self, location: SourceLocation) -> Statement:
        return self._rvalue_builder().delete(location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return self._rvalue_builder().bool_eval(location, negate=negate)

    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._rvalue_builder().unary_plus(location)

    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._rvalue_builder().unary_minus(location)

    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        return self._rvalue_builder().bitwise_invert(location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._rvalue_builder().contains(item, location)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._rvalue_builder().compare(other, op, location)

    def _rvalue_builder(self) -> ExpressionBuilder:
        return var_expression(self.rvalue())
