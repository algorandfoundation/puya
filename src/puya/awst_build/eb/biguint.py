from __future__ import annotations

from typing import TYPE_CHECKING

import attrs
import mypy.nodes
import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    BigUIntAugmentedAssignment,
    BigUIntBinaryOperation,
    BigUIntBinaryOperator,
    BigUIntConstant,
    Expression,
    IntrinsicCall,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    Statement,
)
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import convert_literal_to_expr, expect_operand_wtype
from puya.errors import CodeError, TodoError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class BigUIntClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.biguint_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb]:
                itob_call = _uint64_to_biguint(eb, location)
                return var_expression(itob_call)
            case [Literal(value=int(int_value), source_location=loc)]:
                # TODO: replace with loc with location
                const = BigUIntConstant(value=int_value, source_location=loc)
                return var_expression(const)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class BigUIntExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.biguint_wtype

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "bytes":
                return var_expression(
                    ReinterpretCast(
                        source_location=location, wtype=wtypes.bytes_wtype, expr=self.expr
                    )
                )
        return super().member_access(name, location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        cmp_expr = NumericComparisonExpression(
            lhs=self.expr,
            operator=NumericComparison.eq if negate else NumericComparison.ne,
            # TODO: does this source location make sense?
            rhs=BigUIntConstant(value=0, source_location=location),
            source_location=location,
        )
        return var_expression(cmp_expr)

    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        # unary + is allowed, but for the current types it has no real impact
        # so just expand the existing expression to include the unary operator
        return BigUIntExpressionBuilder(attrs.evolve(self.expr, source_location=location))

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        if other_expr.wtype == self.wtype:
            pass
        elif other_expr.wtype == wtypes.uint64_wtype:
            other_expr = _uint64_to_biguint(other, location)
        elif other_expr.wtype == wtypes.bool_wtype:
            raise TodoError(location, "TODO: support upcast from bool to biguint")
        else:
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=NumericComparison(op.value),
            rhs=other_expr,
        )
        return var_expression(cmp_expr)

    def binary_op(
        self,
        other: ExpressionBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        if other_expr.wtype == self.wtype:
            pass
        elif other_expr.wtype == wtypes.uint64_wtype:
            other_expr = _uint64_to_biguint(other, location)
        elif other_expr.wtype == wtypes.bool_wtype:
            raise TodoError(location, "TODO: support upcast from bool to biguint")
        else:
            return NotImplemented
        lhs = self.expr
        rhs = other_expr
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        biguint_op = _translate_biguint_math_operator(op, location)
        bin_op_expr = BigUIntBinaryOperation(
            source_location=location, left=lhs, op=biguint_op, right=rhs
        )
        return var_expression(bin_op_expr)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        value = convert_literal_to_expr(rhs, self.wtype)
        if value.wtype == self.wtype:
            pass
        elif value.wtype == wtypes.uint64_wtype:
            value = _uint64_to_biguint(rhs, location)
        elif value.wtype == wtypes.bool_wtype:
            raise TodoError(location, "TODO: support upcast from bool to biguint")
        else:
            raise CodeError(
                f"Invalid operand type {value.wtype} for {op.value}= with {self.wtype}", location
            )
        target = self.lvalue()
        biguint_op = _translate_biguint_math_operator(op, location)
        return BigUIntAugmentedAssignment(
            source_location=location,
            target=target,
            value=value,
            op=biguint_op,
        )


def _uint64_to_biguint(
    arg_in: ExpressionBuilder | Expression | Literal, location: SourceLocation
) -> IntrinsicCall:
    arg = expect_operand_wtype(arg_in, wtypes.uint64_wtype)
    itob_call = IntrinsicCall(
        source_location=location,
        wtype=wtypes.biguint_wtype,
        op_code="itob",
        stack_args=[arg],
    )
    return itob_call


def _translate_biguint_math_operator(
    operator: BuilderBinaryOp, loc: SourceLocation
) -> BigUIntBinaryOperator:
    if operator is BuilderBinaryOp.div:
        logger.error(
            (
                "To maintain semantic compatibility with Python, "
                "only the truncating division operator (//) is supported "
            ),
            location=loc,
        )
        # continue traversing code to generate any further errors
        operator = BuilderBinaryOp.floor_div
    try:
        return BigUIntBinaryOperator(operator.value)
    except ValueError as ex:
        raise CodeError(f"Unsupported BigUInt math operator {operator.value}", loc) from ex
