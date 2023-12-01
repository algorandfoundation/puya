from __future__ import annotations

from typing import TYPE_CHECKING

import mypy.nodes
import structlog

from wyvern.awst import wtypes
from wyvern.awst.nodes import (
    BytesAugmentedAssignment,
    BytesBinaryOperation,
    BytesBinaryOperator,
    BytesComparisonExpression,
    BytesConstant,
    BytesDecode,
    BytesEncoding,
    BytesUnaryOperation,
    BytesUnaryOperator,
    EqualityComparison,
    Expression,
    IndexExpression,
    IntrinsicCall,
    IsSubstring,
    Literal,
    SliceExpression,
    Statement,
    UInt64Constant,
)
from wyvern.awst_build.constants import CLS_BYTES_ALIAS
from wyvern.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.awst_build.utils import convert_literal_to_expr, expect_operand_wtype
from wyvern.errors import CodeError, InternalError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from wyvern.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class BytesClassExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.bytes_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=bytes(bytes_val), source_location=loc)]:
                # TODO: replace loc with location
                const = BytesConstant(value=bytes_val, source_location=loc)
                return var_expression(const)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        """Handle self.name"""
        match name:
            case "from_base32":
                return BytesFromEncodedStrBuilder(location, BytesEncoding.base32)
            case "from_base64":
                return BytesFromEncodedStrBuilder(location, BytesEncoding.base64)
            case "from_hex":
                return BytesFromEncodedStrBuilder(location, BytesEncoding.base16)
            case _:
                raise CodeError(
                    f"{name} is not a valid class or static method on {CLS_BYTES_ALIAS}", location
                )


class BytesFromEncodedStrBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation, encoding: BytesEncoding):
        super().__init__(location=location)
        self.encoding = encoding

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=str(encoded_value))]:
                pass
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        match self.encoding:
            case BytesEncoding.base64:
                if not wtypes.valid_base64(encoded_value):
                    raise CodeError("Invalid base64 value", location)
            case BytesEncoding.base32:
                if not wtypes.valid_base32(encoded_value):
                    raise CodeError("Invalid base32 value", location)
            case BytesEncoding.base16:
                encoded_value = encoded_value.upper()
                if not wtypes.valid_base16(encoded_value):
                    raise CodeError("Invalid base16 value", location)
            case _:
                raise InternalError(
                    f"Unhandled bytes encoding for constant construction: {self.encoding}",
                    location,
                )
        expr = BytesDecode(
            source_location=location,
            value=encoded_value,
            encoding=self.encoding,
        )
        return var_expression(expr)


class BytesExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.bytes_wtype

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                len_call = IntrinsicCall.bytes_len(expr=self.expr, source_location=location)
                return var_expression(len_call)
        return super().member_access(name, location)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        index_expr = expect_operand_wtype(index, wtypes.uint64_wtype)
        expr = IndexExpression(
            source_location=location,
            base=self.expr,
            index=index_expr,
            wtype=self.wtype,
        )
        return var_expression(expr)

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if stride is not None:
            raise CodeError("Stride is not supported", location=stride.source_location)

        def eval_slice_component(
            val: ExpressionBuilder | Literal | None,
        ) -> Expression | None:
            match val:
                case Literal(value=int(int_lit)):
                    if int_lit >= 0:
                        return UInt64Constant(
                            value=int_lit,
                            source_location=val.source_location,
                        )
                    else:
                        return IntrinsicCall(
                            wtype=wtypes.uint64_wtype,
                            op_code="-",
                            stack_args=[
                                IntrinsicCall.bytes_len(self.expr, val.source_location),
                                UInt64Constant(
                                    value=abs(int_lit), source_location=val.source_location
                                ),
                            ],
                            source_location=val.source_location,
                        )
                case ExpressionBuilder() as eb:
                    return eb.rvalue()
                case None:
                    return None
                case _:
                    raise CodeError("Unexpected val type")

        return var_expression(
            SliceExpression(
                source_location=location,
                base=self.expr,
                begin_index=eval_slice_component(begin_index),
                end_index=eval_slice_component(end_index),
                wtype=self.wtype,
            )
        )

    def iterate(self) -> Iteration:
        return self.rvalue()

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        len_expr = IntrinsicCall.bytes_len(source_location=location, expr=self.expr)
        len_builder = var_expression(len_expr)
        return len_builder.bool_eval(location, negate=negate)

    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        return BytesExpressionBuilder(
            BytesUnaryOperation(
                expr=self.expr,
                op=BytesUnaryOperator.bit_invert,
                source_location=location,
            )
        )

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        item_expr = expect_operand_wtype(item, wtypes.bytes_wtype)
        is_substring_expr = IsSubstring(
            source_location=location, item=item_expr, sequence=self.expr
        )
        return var_expression(is_substring_expr)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        cmp_expr = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison(op.value),
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
        bytes_op = _translate_binary_bytes_operator(op, location)
        lhs = self.expr
        rhs = other_expr
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        bin_op_expr = BytesBinaryOperation(
            source_location=location, left=lhs, right=rhs, op=bytes_op
        )
        return var_expression(bin_op_expr)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        value = convert_literal_to_expr(rhs, self.wtype)
        bytes_op = _translate_binary_bytes_operator(op, location)
        target = self.lvalue()
        return BytesAugmentedAssignment(
            source_location=location,
            target=target,
            value=value,
            op=bytes_op,
        )


def _translate_binary_bytes_operator(
    operator: BuilderBinaryOp, loc: SourceLocation
) -> BytesBinaryOperator:
    try:
        return BytesBinaryOperator(operator.value)
    except ValueError as ex:
        raise CodeError(f"Unsupported bytes operator {operator.value}", loc) from ex
