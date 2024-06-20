import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    ArrayConcat,
    ArrayExtend,
    Expression,
    ExpressionStatement,
    Statement,
    StringConstant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb._utils import compare_expr_bytes
from puya.awst_build.eb.arc4.base import ARC4TypeBuilder, arc4_bool_bytes
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puya.awst_build.eb.string import StringExpressionBuilder as NativeStringExpressionBuilder
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class StringTypeBuilder(ARC4TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4StringType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case str(literal_value):
                return StringExpressionBuilder(_arc4_encode_str_literal(literal_value, location))
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [InstanceBuilder(pytype=pytypes.StrLiteralType) as eb]:
                return eb.resolve_literal(StringTypeBuilder(location))
            case [InstanceBuilder(pytype=pytypes.StringType)]:
                return _expect_string(args[0], location)
            case []:
                return StringExpressionBuilder(_arc4_encode_str_literal("", location))
        raise CodeError("invalid/unhandled arguments", location)


def _arc4_encode_str_literal(value: str, location: SourceLocation) -> Expression:
    return ARC4Encode(
        value=StringConstant(value=value, source_location=location),
        wtype=wtypes.arc4_string_alias,
        source_location=location,
    )


def _expect_string(expr: NodeBuilder, location: SourceLocation) -> InstanceBuilder:
    expr = require_instance_builder(expr)
    match expr:
        case InstanceBuilder(pytype=pytypes.StrLiteralType) as eb:
            return eb.resolve_literal(StringTypeBuilder(location))
        case InstanceBuilder(pytype=pytypes.StringType) as eb:
            string_expr = eb.resolve()
            return StringExpressionBuilder(
                ARC4Encode(
                    value=string_expr, wtype=wtypes.arc4_string_alias, source_location=location
                )
            )
        case InstanceBuilder(pytype=pytypes.ARC4StringType) as eb:
            return eb
        case _:
            raise CodeError("invalid/unhandled arguments", location)


class StringExpressionBuilder(
    NotIterableInstanceExpressionBuilder, BytesBackedInstanceExpressionBuilder
):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.ARC4StringType, expr)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        match op:
            case BuilderBinaryOp.add:
                return ExpressionStatement(
                    expr=ArrayExtend(
                        base=self.resolve(),
                        other=_expect_string(rhs, rhs.source_location).resolve(),
                        source_location=location,
                        wtype=wtypes.arc4_string_alias,
                    )
                )
            case _:
                raise CodeError("unsupported operator", location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        match op:
            case BuilderBinaryOp.add:
                lhs = self.resolve()
                rhs = _expect_string(other, other.source_location).resolve()
                if reverse:
                    (lhs, rhs) = (rhs, lhs)
                return StringExpressionBuilder(
                    ArrayConcat(
                        left=lhs,
                        right=rhs,
                        source_location=location,
                        wtype=wtypes.arc4_string_alias,
                    )
                )

            case _:
                return super().binary_op(other, op, location, reverse=reverse)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        match other:
            case LiteralBuilder(pytype=pytypes.StrLiteralType) as rhs_eb:
                lhs: InstanceBuilder = self
                rhs = rhs_eb.resolve_literal(StringTypeBuilder(location))
            case InstanceBuilder(pytype=pytypes.StringType) as eb:
                lhs = _string_to_native(self, location)
                rhs = eb
            case InstanceBuilder(pytype=pytypes.ARC4StringType) as eb:
                lhs = self
                rhs = eb
            case _:
                return NotImplemented

        return compare_expr_bytes(
            lhs=lhs.resolve(), op=op, rhs=rhs.resolve(), source_location=location
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(self, false_bytes=b"\x00\x00", location=location, negate=negate)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                return _string_to_native(self, location)
            case _:
                return super().member_access(name, location)


def _string_to_native(
    builder: InstanceBuilder, location: SourceLocation
) -> NativeStringExpressionBuilder:
    assert builder.pytype == pytypes.ARC4StringType
    return NativeStringExpressionBuilder(
        ARC4Decode(
            value=builder.resolve(),
            wtype=pytypes.StringType.wtype,
            source_location=location,
        )
    )
