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
    BuilderUnaryOp,
    FunctionBuilder,
    InstanceBuilder,
    InstanceExpressionBuilder,
    Iteration,
    NodeBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import (
    convert_literal_to_builder,
    expect_operand_type,
)
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class BytesClassExpressionBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.BytesType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case []:
                value: Expression = BytesConstant(
                    value=b"", encoding=BytesEncoding.unknown, source_location=location
                )
            case [Literal(value=bytes(literal_value))]:
                value = BytesConstant(
                    value=literal_value, encoding=BytesEncoding.unknown, source_location=location
                )
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                value = BytesConstant(
                    value=b"", encoding=BytesEncoding.unknown, source_location=location
                )
        return BytesExpressionBuilder(value)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
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
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
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


class BytesExpressionBuilder(InstanceExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.BytesType, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "length":
                len_call = intrinsic_factory.bytes_len(expr=self.expr, loc=location)
                return UInt64ExpressionBuilder(len_call)
        return super().member_access(name, location)

    @typing.override
    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        index_expr = expect_operand_type(index, pytypes.UInt64Type).rvalue()
        expr = IndexExpression(
            source_location=location,
            base=self.expr,
            index=index_expr,
            wtype=self.pytype.wtype,
        )
        return BytesExpressionBuilder(expr)

    @typing.override
    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        if stride is not None:
            raise CodeError("Stride is not supported", location=stride.source_location)

        slice_expr: Expression = IntersectionSliceExpression(
            base=self.expr,
            begin_index=_eval_slice_component(begin_index),
            end_index=_eval_slice_component(end_index),
            wtype=self.pytype.wtype,
            source_location=location,
        )
        return BytesExpressionBuilder(slice_expr)

    @typing.override
    def iterate(self) -> Iteration:
        return self.rvalue()

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        len_expr = intrinsic_factory.bytes_len(self.expr, location)
        len_builder = UInt64ExpressionBuilder(len_expr)
        return len_builder.bool_eval(location, negate=negate)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        if op == BuilderUnaryOp.bit_invert:
            return BytesExpressionBuilder(
                BytesUnaryOperation(
                    expr=self.expr,
                    op=BytesUnaryOperator.bit_invert,
                    source_location=location,
                )
            )
        return super().unary_op(op, location)

    @typing.override
    def contains(
        self, item: InstanceBuilder | Literal, location: SourceLocation
    ) -> InstanceBuilder:
        item_expr = expect_operand_type(item, pytypes.BytesType).rvalue()
        is_substring_expr = SubroutineCallExpression(
            target=FreeSubroutineTarget(module_name="algopy_lib_bytes", name="is_substring"),
            args=[CallArg(value=item_expr, name=None), CallArg(value=self.expr, name=None)],
            wtype=wtypes.bool_wtype,
            source_location=location,
        )
        return BoolExpressionBuilder(is_substring_expr)

    @typing.override
    def compare(
        self, other: InstanceBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        if other.pytype != self.pytype:
            return NotImplemented
        cmp_expr = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison(op.value),
            rhs=other.rvalue(),
        )
        return BoolExpressionBuilder(cmp_expr)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        # TODO: missing type check
        bytes_op = _translate_binary_bytes_operator(op, location)
        lhs = self.expr
        rhs = other.rvalue()
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        bin_op_expr = BytesBinaryOperation(
            source_location=location, left=lhs, right=rhs, op=bytes_op
        )
        return BytesExpressionBuilder(bin_op_expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder | Literal, location: SourceLocation
    ) -> Statement:
        rhs = convert_literal_to_builder(rhs, self.pytype)
        # TODO: missing type check
        bytes_op = _translate_binary_bytes_operator(op, location)
        target = self.lvalue()
        return BytesAugmentedAssignment(
            target=target,
            op=bytes_op,
            value=rhs.rvalue(),
            source_location=location,
        )


def _translate_binary_bytes_operator(
    operator: BuilderBinaryOp, loc: SourceLocation
) -> BytesBinaryOperator:
    try:
        return BytesBinaryOperator(operator.value)
    except ValueError as ex:
        raise CodeError(f"Unsupported bytes operator {operator.value}", loc) from ex


def _eval_slice_component(val: NodeBuilder | Literal | None) -> Expression | None | int:
    match val:
        case None:
            return None
        case Literal(value=int(int_value)):
            return int_value
    return expect_operand_type(val, pytypes.UInt64Type).rvalue()
