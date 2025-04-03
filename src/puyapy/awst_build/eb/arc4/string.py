import typing
from collections.abc import Sequence

from puya import algo_constants, log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    ArrayConcat,
    BytesAugmentedAssignment,
    BytesBinaryOperator,
    Expression,
    Statement,
    StringConstant,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puyapy.awst_build.eb._utils import compare_expr_bytes, dummy_statement
from puyapy.awst_build.eb.arc4._base import ARC4TypeBuilder, arc4_bool_bytes
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puyapy.awst_build.eb.string import StringExpressionBuilder

__all__ = [
    "ARC4StringTypeBuilder",
    "ARC4StringExpressionBuilder",
]

logger = log.get_logger(__name__)


class ARC4StringTypeBuilder(ARC4TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4StringType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case str(literal_value):
                try:
                    bytes_value = literal_value.encode("utf8")
                except UnicodeEncodeError as ex:
                    logger.error(  # noqa: TRY400
                        f"invalid UTF-8 string (encoding error: {ex})",
                        location=literal.source_location,
                    )
                else:
                    if len(bytes_value) > (algo_constants.MAX_BYTES_LENGTH - 2):
                        logger.error(
                            "encoded string exceeds max byte array length",
                            location=literal.source_location,
                        )
                return _arc4_str_literal(literal_value, location)
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
            case InstanceBuilder(pytype=pytypes.StrLiteralType):
                return arg.resolve_literal(ARC4StringTypeBuilder(location))
            case None:
                return _arc4_str_literal("", location)
            case _:
                arg = expect.argument_of_type_else_dummy(arg, pytypes.StringType)
                return _from_native(arg, location)


class ARC4StringExpressionBuilder(
    NotIterableInstanceExpressionBuilder, BytesBackedInstanceExpressionBuilder
):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.ARC4StringType, expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        if op != BuilderBinaryOp.add:
            logger.error(f"unsupported operator for type: {op.value!r}", location=location)
            return dummy_statement(location)

        rhs = rhs.resolve_literal(ARC4StringTypeBuilder(rhs.source_location))
        if pytypes.StringType <= rhs.pytype:
            value = _from_native(rhs, rhs.source_location).resolve()
        else:
            value = expect.argument_of_type_else_dummy(rhs, self.pytype).resolve()

        return BytesAugmentedAssignment(
            target=self.resolve_lvalue(),
            op=BytesBinaryOperator.add,
            value=value,
            source_location=location,
        )

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        if op != BuilderBinaryOp.add:
            return NotImplemented

        other = other.resolve_literal(ARC4StringTypeBuilder(other.source_location))
        if pytypes.ARC4StringType <= other.pytype:
            other_expr = other.resolve()
        elif pytypes.StringType <= other.pytype:
            other_expr = _from_native(other, other.source_location).resolve()
        else:
            return NotImplemented

        lhs = self.resolve()
        rhs = other_expr
        if reverse:
            (lhs, rhs) = (rhs, lhs)

        return ARC4StringExpressionBuilder(
            ArrayConcat(left=lhs, right=rhs, source_location=location)
        )

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.resolve_literal(ARC4StringTypeBuilder(other.source_location))
        if pytypes.ARC4StringType <= other.pytype:
            lhs: InstanceBuilder = self
        elif pytypes.StringType <= other.pytype:
            # when comparing arc4 to native, easier to convert by stripping length prefix
            lhs = _string_to_native(self, self.source_location)
        else:
            return NotImplemented
        return compare_expr_bytes(
            lhs=lhs.resolve(),
            op=op,
            rhs=other.resolve(),
            source_location=location,
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self,
            false_bytes=b"\x00\x00",
            negate=negate,
            location=location,
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                return _string_to_native(self, location)
            case _:
                return super().member_access(name, location)


def _string_to_native(
    builder: InstanceBuilder, location: SourceLocation
) -> StringExpressionBuilder:
    assert pytypes.ARC4StringType <= builder.pytype
    return StringExpressionBuilder(
        ARC4Decode(
            value=builder.resolve(),
            wtype=pytypes.StringType.wtype,
            source_location=location,
        )
    )


def _arc4_str_literal(value: str, location: SourceLocation) -> InstanceBuilder:
    return ARC4StringExpressionBuilder(
        StringConstant(value=value, source_location=location, wtype=wtypes.arc4_string_alias)
    )


def _from_native(eb: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
    assert pytypes.StringType <= eb.pytype
    return ARC4StringExpressionBuilder(
        ARC4Encode(
            value=eb.resolve(),
            wtype=wtypes.arc4_string_alias,
            source_location=location,
        )
    )
