from __future__ import annotations

import base64
import typing

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesAugmentedAssignment,
    BytesBinaryOperation,
    BytesBinaryOperator,
    BytesComparisonExpression,
    BytesConstant,
    BytesEncoding,
    BytesUnaryOperation,
    BytesUnaryOperator,
    CallArg,
    EqualityComparison,
    Expression,
    FreeSubroutineTarget,
    IndexExpression,
    IntersectionSliceExpression,
    Literal,
    Statement,
    SubroutineCallExpression,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.constants import CLS_BYTES_ALIAS
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    FunctionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import (
    convert_literal,
    convert_literal_to_expr,
    expect_operand_wtype,
)
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class BytesClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.BytesType, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                value: Expression = BytesConstant(value=b"", source_location=location)
            case [Literal(value=bytes(literal_value))]:
                value = BytesConstant(value=literal_value, source_location=location)
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                value = BytesConstant(value=b"", source_location=location)
        return BytesExpressionBuilder(value)

    @typing.override
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


class BytesFromEncodedStrBuilder(FunctionBuilder):
    def __init__(self, location: SourceLocation, encoding: BytesEncoding):
        super().__init__(location=location)
        self.encoding = encoding

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
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
                bytes_value = base64.b64decode(encoded_value)
            case BytesEncoding.base32:
                if not wtypes.valid_base32(encoded_value):
                    raise CodeError("Invalid base32 value", location)
                bytes_value = base64.b32decode(encoded_value)
            case BytesEncoding.base16:
                encoded_value = encoded_value.upper()
                if not wtypes.valid_base16(encoded_value):
                    raise CodeError("Invalid base16 value", location)
                bytes_value = base64.b16decode(encoded_value)
            case _:
                raise InternalError(
                    f"Unhandled bytes encoding for constant construction: {self.encoding}",
                    location,
                )
        expr = BytesConstant(
            source_location=location,
            value=bytes_value,
            encoding=self.encoding,
        )
        return BytesExpressionBuilder(expr)


class BytesExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.BytesType, expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                len_call = intrinsic_factory.bytes_len(expr=self.expr, loc=location)
                return UInt64ExpressionBuilder(len_call)
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
        return BytesExpressionBuilder(expr)

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if stride is not None:
            raise CodeError("Stride is not supported", location=stride.source_location)

        slice_expr: Expression = IntersectionSliceExpression(
            base=self.expr,
            begin_index=_eval_slice_component(begin_index),
            end_index=_eval_slice_component(end_index),
            wtype=self.wtype,
            source_location=location,
        )
        return BytesExpressionBuilder(slice_expr)

    def iterate(self) -> Iteration:
        return self.rvalue()

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        len_expr = intrinsic_factory.bytes_len(self.expr, location)
        len_builder = UInt64ExpressionBuilder(len_expr)
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
        is_substring_expr = SubroutineCallExpression(
            target=FreeSubroutineTarget(module_name="algopy_lib_bytes", name="is_substring"),
            args=[CallArg(value=item_expr, name=None), CallArg(value=self.expr, name=None)],
            wtype=wtypes.bool_wtype,
            source_location=location,
        )
        return BoolExpressionBuilder(is_substring_expr)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        if other_expr.wtype != self.wtype:
            return NotImplemented
        cmp_expr = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison(op.value),
            rhs=other_expr,
        )
        return BoolExpressionBuilder(cmp_expr)

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
        return BytesExpressionBuilder(bin_op_expr)

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


def _eval_slice_component(val: ExpressionBuilder | Literal | None) -> Expression | None | int:
    match val:
        case None:
            return None
        case Literal(value=int(int_value)):
            return int_value
    return expect_operand_wtype(val, wtypes.uint64_wtype)
