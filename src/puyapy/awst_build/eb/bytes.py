import base64
import typing
from collections.abc import Sequence

from puya import algo_constants, log, utils
from puya.awst.nodes import (
    BytesAugmentedAssignment,
    BytesBinaryOperation,
    BytesBinaryOperator,
    BytesConstant,
    BytesEncoding,
    BytesUnaryOperation,
    BytesUnaryOperator,
    CallArg,
    Expression,
    IndexExpression,
    IntersectionSliceExpression,
    PuyaLibCall,
    PuyaLibFunction,
    Statement,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, InstanceExpressionBuilder
from puyapy.awst_build.eb._utils import (
    compare_bytes,
    dummy_statement,
    dummy_value,
    resolve_negative_literal_index,
)
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

logger = log.get_logger(__name__)


class BytesTypeBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.BytesType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case bytes(literal_value):
                if len(literal_value) > algo_constants.MAX_BYTES_LENGTH:
                    logger.error(
                        "bytes constant exceeds max length", location=literal.source_location
                    )

                expr = BytesConstant(
                    value=literal_value, encoding=BytesEncoding.unknown, source_location=location
                )
                return BytesExpressionBuilder(expr)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        match arg:
            case InstanceBuilder(pytype=pytypes.BytesLiteralType):
                return arg.resolve_literal(BytesTypeBuilder(location))
            case None:
                value = BytesConstant(
                    value=b"", encoding=BytesEncoding.unknown, source_location=location
                )
                return BytesExpressionBuilder(value)
            case other:
                return expect.not_this_type(
                    other, default=expect.default_dummy_value(self.produces())
                )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        """Handle self.name"""
        match name:
            case "from_base32":
                return _FromEncodedStr(location, BytesEncoding.base32)
            case "from_base64":
                return _FromEncodedStr(location, BytesEncoding.base64)
            case "from_hex":
                return _FromEncodedStr(location, BytesEncoding.base16)
            case _:
                return super().member_access(name, location)


class _FromEncodedStr(FunctionBuilder):
    def __init__(
        self,
        location: SourceLocation,
        encoding: typing.Literal[BytesEncoding.base16, BytesEncoding.base32, BytesEncoding.base64],
    ):
        super().__init__(location=location)
        self.encoding = encoding

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_none)
        if arg is not None:
            encoded_value = expect.simple_string_literal(arg, default=expect.default_none)
            if encoded_value is not None:
                match self.encoding:
                    case BytesEncoding.base64:
                        if not utils.valid_base64(encoded_value):
                            logger.error("invalid base64 value", location=arg.source_location)
                            bytes_value = b""
                        else:
                            bytes_value = base64.b64decode(encoded_value)
                    case BytesEncoding.base32:
                        if not utils.valid_base32(encoded_value):
                            logger.error("invalid base32 value", location=arg.source_location)
                            bytes_value = b""
                        else:
                            bytes_value = base64.b32decode(encoded_value)
                    case BytesEncoding.base16:
                        encoded_value = encoded_value.upper()
                        if not utils.valid_base16(encoded_value):
                            logger.error("invalid base16 value", location=arg.source_location)
                            bytes_value = b""
                        else:
                            bytes_value = base64.b16decode(encoded_value)
                    case _:
                        typing.assert_never(self.encoding)
                expr = BytesConstant(
                    source_location=location,
                    value=bytes_value,
                    encoding=self.encoding,
                )
                return BytesExpressionBuilder(expr)
        return dummy_value(pytypes.BytesType, location)


class BytesExpressionBuilder(InstanceExpressionBuilder[pytypes.RuntimeType]):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.BytesType, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return self.resolve()

    def length(self, location: SourceLocation) -> InstanceBuilder:
        len_call = intrinsic_factory.bytes_len(expr=self.resolve(), loc=location)
        return UInt64ExpressionBuilder(len_call)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> InstanceBuilder:
        match name:
            case "length":
                return self.length(location)
        raise CodeError(f"unrecognised member of {self.pytype}: {name}", location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        length = self.length(location)
        index = resolve_negative_literal_index(index, length, location)
        expr = IndexExpression(
            base=self.resolve(),
            index=index.resolve(),
            wtype=self.pytype.wtype,
            source_location=location,
        )
        return BytesExpressionBuilder(expr)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        if stride is not None:
            logger.error("stride is not supported", location=stride.source_location)

        slice_expr: Expression = IntersectionSliceExpression(
            base=self.resolve(),
            begin_index=_eval_slice_component(begin_index),
            end_index=_eval_slice_component(end_index),
            wtype=self.pytype.wtype,
            source_location=location,
        )
        return BytesExpressionBuilder(slice_expr)

    @typing.override
    def iterate(self) -> Expression:
        return self.resolve()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return pytypes.BytesType

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        len_expr = intrinsic_factory.bytes_len(self.resolve(), location)
        len_builder = UInt64ExpressionBuilder(len_expr)
        return len_builder.bool_eval(location, negate=negate)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        if op == BuilderUnaryOp.bit_invert:
            return BytesExpressionBuilder(
                BytesUnaryOperation(
                    expr=self.resolve(),
                    op=BytesUnaryOperator.bit_invert,
                    source_location=location,
                )
            )
        return super().unary_op(op, location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        item_expr = expect.argument_of_type_else_dummy(
            item, pytypes.BytesType, resolve_literal=True
        ).resolve()
        is_substring_expr = PuyaLibCall(
            func=PuyaLibFunction.is_substring,
            args=[CallArg(value=item_expr, name=None), CallArg(value=self.resolve(), name=None)],
            source_location=location,
        )
        return BoolExpressionBuilder(is_substring_expr)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.resolve_literal(converter=BytesTypeBuilder(other.source_location))
        return compare_bytes(self=self, op=op, other=other, source_location=location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        bytes_op = _translate_binary_bytes_operator(op)
        if bytes_op is None:
            return NotImplemented

        other = other.resolve_literal(converter=BytesTypeBuilder(other.source_location))
        if not (pytypes.BytesType <= other.pytype):
            return NotImplemented

        lhs = self.resolve()
        rhs = other.resolve()
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        bin_op_expr = BytesBinaryOperation(
            source_location=location, left=lhs, right=rhs, op=bytes_op
        )
        return BytesExpressionBuilder(bin_op_expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        bytes_op = _translate_binary_bytes_operator(op)
        if bytes_op is None:
            logger.error(f"unsupported operator for type: {op.value!r}", location=location)
            return dummy_statement(location)

        rhs = expect.argument_of_type_else_dummy(rhs, self.pytype, resolve_literal=True)
        target = self.resolve_lvalue()
        return BytesAugmentedAssignment(
            target=target,
            op=bytes_op,
            value=rhs.resolve(),
            source_location=location,
        )


def _translate_binary_bytes_operator(operator: BuilderBinaryOp) -> BytesBinaryOperator | None:
    try:
        return BytesBinaryOperator(operator.value)
    except ValueError:
        return None


def _eval_slice_component(val: NodeBuilder | None) -> Expression | None | int:
    match val:
        case None:
            return None
        case LiteralBuilder(value=int(int_value)):
            return int_value
    return expect.argument_of_type_else_dummy(val, pytypes.UInt64Type).resolve()
