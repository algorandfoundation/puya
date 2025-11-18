import base64
import typing
from collections.abc import Callable, Sequence

import attrs

from puya import log, utils
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesAugmentedAssignment,
    BytesBinaryOperation,
    BytesBinaryOperator,
    BytesConstant,
    BytesEncoding,
    BytesUnaryOperation,
    BytesUnaryOperator,
    CallArg,
    CheckedMaybe,
    Expression,
    IndexExpression,
    IntersectionSliceExpression,
    IntrinsicCall,
    NumericComparison,
    NumericComparisonExpression,
    PuyaLibCall,
    PuyaLibFunction,
    ReinterpretCast,
    Statement,
    UInt64Constant,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.arc4_utils import pytype_to_arc4_pytype
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, GenericTypeBuilder
from puyapy.awst_build.eb._bytes_backed import (
    BytesBackedInstanceExpressionBuilder,
    BytesBackedTypeBuilder,
)
from puyapy.awst_build.eb._utils import (
    compare_bytes,
    constant_bool_and_error,
    dummy_statement,
    dummy_value,
    resolve_negative_literal_index,
)
from puyapy.awst_build.eb._validatable import ValidateEncoding
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder, BytesTypeBuilder
from puyapy.awst_build.eb.factories import builder_for_instance, builder_for_type
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
)
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

logger = log.get_logger(__name__)


class FixedBytesGenericTypeBuilder(GenericTypeBuilder):
    """Handles the generic FixedBytes type (before parameterization)."""

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(
            args,
            location,
            default=expect.default_raise,
            missing_message="an argument is required when no type annotation is supplied",
        )
        arg = expect.argument_of_type(
            arg, pytypes.BytesType, pytypes.BytesLiteralType, default=expect.default_raise
        )
        arg = arg.resolve_literal(converter=BytesTypeBuilder(arg.source_location))
        bytes_expr = arg.resolve()
        if not isinstance(bytes_expr, BytesConstant):
            raise CodeError(
                "argument must be constant when type annotation is not provided", location
            )
        length = len(bytes_expr.value)
        parameterised_typ = pytypes.FixedBytesType(length=length)
        typ_builder = builder_for_type(parameterised_typ, location)
        return typ_builder.call(args, arg_kinds, arg_names, location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        """Handle type-level member access like FixedBytes.from_hex()"""
        match name:
            case "from_bytes":
                return _FromBytesWithInferredLength(location)
            case "from_base32":
                return _FromEncodedStrWithInferredLength(location, BytesEncoding.base32)
            case "from_base64":
                return _FromEncodedStrWithInferredLength(location, BytesEncoding.base64)
            case "from_hex":
                return _FromEncodedStrWithInferredLength(location, BytesEncoding.base16)
            case _:
                return super().member_access(name, location)


class FixedBytesTypeBuilder(BytesBackedTypeBuilder[pytypes.FixedBytesType]):
    """Handles parameterized FixedBytes types like FixedBytes[Literal[32]]."""

    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.FixedBytesType)
        super().__init__(typ, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        pytype = self.produces()
        match literal.value:
            case bytes(literal_value):
                if len(literal_value) != pytype.length:
                    logger.error(
                        f"invalid bytes constant length of {len(literal_value)}, "
                        f"expected {pytype.length}",
                        location=literal.source_location,
                    )
                    literal_value = b" " * pytype.length
                expr = BytesConstant(
                    value=literal_value,
                    encoding=BytesEncoding.unknown,
                    wtype=pytype.wtype,
                    source_location=location,
                )
                return FixedBytesExpressionBuilder(expr, pytype)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        pytype = self.produces()
        arg = expect.at_most_one_arg_of_type(
            args, [pytypes.BytesLiteralType, pytypes.BytesType], location
        )
        match arg:
            case InstanceBuilder(pytype=pytypes.BytesLiteralType):
                return arg.resolve_literal(converter=FixedBytesTypeBuilder(pytype, location))
            case InstanceBuilder(pytype=pytypes.BytesType):
                return _checked_size(arg, pytype, location)
            case _:
                if pytype.length == 0:
                    empty_expr: Expression = BytesConstant(
                        value=b"",
                        encoding=BytesEncoding.unknown,
                        wtype=pytype.wtype,
                        source_location=location,
                    )
                else:
                    length_const = UInt64Constant(value=pytype.length, source_location=location)
                    empty_expr = IntrinsicCall(
                        op_code="bzero",
                        stack_args=[length_const],
                        wtype=pytype.wtype,
                        source_location=location,
                    )
                return FixedBytesExpressionBuilder(empty_expr, pytype)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        """Handle type-level member access like FixedBytes[32].from_hex()"""
        pytype = self.produces()
        match name:
            case "from_base32":
                return _FromEncodedStr(location, BytesEncoding.base32, pytype)
            case "from_base64":
                return _FromEncodedStr(location, BytesEncoding.base64, pytype)
            case "from_hex":
                return _FromEncodedStr(location, BytesEncoding.base16, pytype)
            case _:
                return super().member_access(name, location)


def _checked_size(
    arg: InstanceBuilder, pytype: pytypes.FixedBytesType, location: SourceLocation
) -> InstanceBuilder:
    assert arg.pytype == pytypes.BytesType, "unexpected arg type"
    arg_expr = arg.single_eval().resolve()
    length_const = UInt64Constant(value=pytype.length, source_location=location)
    fixed_bytes_expr = ReinterpretCast(
        expr=arg_expr,
        wtype=pytype.wtype,
        source_location=location,
    )
    length_condition = NumericComparisonExpression(
        lhs=intrinsic_factory.bytes_len(expr=arg_expr, loc=location),
        operator=NumericComparison.eq,
        rhs=length_const,
        source_location=location,
    )
    checked_expr = CheckedMaybe.from_tuple_items(
        expr=fixed_bytes_expr,
        check=length_condition,
        comment=f"expected bytes to be length {pytype.length}",
        source_location=location,
    )
    return FixedBytesExpressionBuilder(checked_expr, pytype)


def get_byte_value_from_encoded_str[T](
    arg: NodeBuilder,
    encoding: typing.Literal[BytesEncoding.base16, BytesEncoding.base32, BytesEncoding.base64],
    *,
    default: Callable[[str, SourceLocation], T],
) -> bytes | T:
    def _handle_error(msg: str) -> T:
        logger.error(msg, location=arg.source_location)
        result = default(msg, arg.source_location)
        return result

    encoded_value = expect.simple_string_literal(arg, default=default)
    if isinstance(encoded_value, str):
        match encoding:
            case BytesEncoding.base64:
                if not utils.valid_base64(encoded_value):
                    return _handle_error("invalid base64 value")
                else:
                    return base64.b64decode(encoded_value)
            case BytesEncoding.base32:
                if not utils.valid_base32(encoded_value):
                    return _handle_error("invalid base32 value")
                else:
                    return base64.b32decode(encoded_value)
            case BytesEncoding.base16:
                encoded_value = encoded_value.upper()
                if not utils.valid_base16(encoded_value):
                    return _handle_error("invalid base16 value")
                else:
                    return base64.b16decode(encoded_value)
            case _:
                typing.assert_never(encoding)
    return encoded_value


class _FromBytesWithInferredLength(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type(
            args, pytypes.BytesType, location, default=expect.default_raise, resolve_literal=True
        )
        bytes_expr = arg.resolve()
        if not isinstance(bytes_expr, BytesConstant):
            raise CodeError(
                "requires a literal value to be passed in when type annotation is not provided",
                location,
            )

        length = len(bytes_expr.value)
        parameterised_typ = pytypes.FixedBytesType(length=length)
        bytes_expr = attrs.evolve(bytes_expr, wtype=parameterised_typ.wtype)
        return FixedBytesExpressionBuilder(bytes_expr, parameterised_typ)


class _FromEncodedStrWithInferredLength(FunctionBuilder):
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
        arg = expect.exactly_one_arg(args, location, default=expect.default_raise)

        bytes_value = get_byte_value_from_encoded_str(
            arg, self.encoding, default=expect.default_raise
        )
        length = len(bytes_value)
        parameterised_typ = pytypes.FixedBytesType(length=length)

        expr = BytesConstant(
            value=bytes_value,
            encoding=self.encoding,
            wtype=parameterised_typ.wtype,
            source_location=location,
        )
        return FixedBytesExpressionBuilder(expr, parameterised_typ)


class _FromEncodedStr(FunctionBuilder):
    def __init__(
        self,
        location: SourceLocation,
        encoding: typing.Literal[BytesEncoding.base16, BytesEncoding.base32, BytesEncoding.base64],
        pytype: pytypes.FixedBytesType,
    ):
        super().__init__(location=location)
        self.encoding = encoding
        self.result_pytype = pytype

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_none)
        if arg is None:
            return dummy_value(self.result_pytype, location)

        bytes_value = get_byte_value_from_encoded_str(
            arg, self.encoding, default=expect.default_none
        )
        if bytes_value is None:
            bytes_value = b" " * self.result_pytype.length
        elif len(bytes_value) != self.result_pytype.length:
            logger.error(
                f"decoded bytes length {len(bytes_value)} does not match "
                f"FixedBytes length {self.result_pytype.length}",
                location=arg.source_location,
            )
            bytes_value = b" " * self.result_pytype.length

        expr = BytesConstant(
            value=bytes_value,
            encoding=self.encoding,
            wtype=self.result_pytype.wtype,
            source_location=location,
        )
        return FixedBytesExpressionBuilder(expr, self.result_pytype)


class FixedBytesExpressionBuilder(
    BytesBackedInstanceExpressionBuilder[pytypes.FixedBytesType], StaticSizedCollectionBuilder
):
    """Handles runtime operations on FixedBytes instances."""

    def __init__(self, expr: Expression, pytype: pytypes.PyType):
        assert isinstance(pytype, pytypes.FixedBytesType)
        super().__init__(pytype, expr)

    def length(self, location: SourceLocation) -> InstanceBuilder:
        return UInt64ExpressionBuilder(
            UInt64Constant(value=self.pytype.length, source_location=location)
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return self.length(location)
            case "validate":
                arc4_pytype = pytype_to_arc4_pytype(
                    self.pytype,
                    on_error="fail",
                    encode_resource_types=True,
                    source_location=location,
                )
                return ValidateEncoding(self.resolve(), arc4_pytype, location)
            case _:
                # Delegate to BytesBackedInstanceExpressionBuilder for .bytes property
                return super().member_access(name, location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        length = self.length(location)
        index = resolve_negative_literal_index(index, length, location)
        expr = IndexExpression(
            base=self.resolve(),
            index=index.resolve(),
            wtype=wtypes.bytes_wtype,
            source_location=location,
        )
        # Indexing returns a single byte as Bytes type
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

        slice_expr = IntersectionSliceExpression(
            base=self.resolve(),
            begin_index=_eval_slice_component(begin_index),
            end_index=_eval_slice_component(end_index),
            wtype=wtypes.bytes_wtype,
            source_location=location,
        )
        # Slicing returns Bytes type (not FixedBytes since length may change)
        return BytesExpressionBuilder(slice_expr)

    @typing.override
    def iterate(self) -> Expression:
        return self.resolve()

    @typing.override
    def iterate_static(self) -> Sequence[InstanceBuilder]:
        base = self.single_eval().resolve()
        return [
            BytesExpressionBuilder(
                IndexExpression(
                    base=base,
                    index=UInt64Constant(value=idx, source_location=self.source_location),
                    wtype=wtypes.bytes_wtype,
                    source_location=self.source_location,
                ),
            )
            for idx in range(self.pytype.length)
        ]

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return pytypes.BytesType

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(
            value=self.pytype.length > 0, location=location, negate=negate
        )

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        if op == BuilderUnaryOp.bit_invert:
            return FixedBytesExpressionBuilder(
                BytesUnaryOperation(
                    expr=self.resolve(),
                    op=BytesUnaryOperator.bit_invert,
                    source_location=location,
                ),
                self.pytype,
            )
        return super().unary_op(op, location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        if isinstance(item.pytype, pytypes.FixedBytesType):
            # this will cast to unsized bytes, not strictly required currently, but that is
            # the specified argument type of `PuyaLibFunction.is_substring`
            item_expr = item.to_bytes(location)
        else:
            item_expr = expect.argument_of_type_else_dummy(
                item, pytypes.BytesType, resolve_literal=True
            ).resolve()

        is_substring_expr = PuyaLibCall(
            func=PuyaLibFunction.is_substring,
            args=[
                CallArg(value=item_expr, name=None),
                CallArg(value=self.to_bytes(location), name=None),
            ],
            source_location=location,
        )
        return BoolExpressionBuilder(is_substring_expr)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        if isinstance(other.pytype, pytypes.FixedBytesType):
            if other.pytype.length != self.pytype.length and op in (
                BuilderComparisonOp.eq,
                BuilderComparisonOp.ne,
            ):
                return constant_bool_and_error(
                    value=False, location=location, negate=op == BuilderComparisonOp.ne
                )
            this: InstanceBuilder = self
        else:
            this = self.bytes(location)
            other = other.resolve_literal(BytesTypeBuilder(location))
        return compare_bytes(self=this, op=op, other=other, source_location=location)

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
            return NotImplemented  # type: ignore[no-any-return]

        lhs: InstanceBuilder = self
        rhs = other.resolve_literal(BytesTypeBuilder(location))

        if not (pytypes.BytesType <= rhs.pytype or isinstance(rhs.pytype, pytypes.FixedBytesType)):
            return NotImplemented  # type: ignore[no-any-return]

        # Maintain fixed length type if both operands match and operation is not concatenation
        if bytes_op != BytesBinaryOperator.add and self.pytype == rhs.pytype:
            expr_type: pytypes.RuntimeType = self.pytype
        else:
            expr_type = pytypes.BytesType

        if reverse:
            (lhs, rhs) = (rhs, lhs)
        bin_op_expr = BytesBinaryOperation(
            left=lhs.resolve(),
            op=bytes_op,
            right=rhs.resolve(),
            wtype=expr_type.wtype,
            source_location=location,
        )

        return builder_for_instance(expr_type, bin_op_expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        bytes_op = _translate_binary_bytes_operator(op)
        match bytes_op:
            case None | BytesBinaryOperator.add:
                logger.error(f"unsupported operator for type: {op.value!r}", location=location)
                return dummy_statement(location)
            case supported:
                typing.assert_type(
                    supported,
                    typing.Literal[
                        BytesBinaryOperator.bit_or,
                        BytesBinaryOperator.bit_xor,
                        BytesBinaryOperator.bit_and,
                    ],
                )

        target = self.resolve_lvalue()
        match rhs:
            case InstanceBuilder(pytype=pytypes.BytesLiteralType):
                other = rhs.resolve_literal(
                    FixedBytesTypeBuilder(self.pytype, rhs.source_location)
                ).resolve()
            case InstanceBuilder(pytype=pytypes.FixedBytesType()):
                other = rhs.resolve()
            case InstanceBuilder(pytype=pytypes.BytesType):
                other = _checked_size(rhs, self.pytype, rhs.source_location).resolve()
            case _:
                expect.not_this_type(rhs, default=expect.default_none)
                return dummy_statement(location)

        return BytesAugmentedAssignment(
            target=target,
            op=bytes_op,
            value=other,
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
