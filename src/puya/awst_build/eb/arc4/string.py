from __future__ import annotations

import typing

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
from puya.awst_build.eb._base import (
    NotIterableInstanceExpressionBuilder,
)
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb._utils import compare_expr_bytes
from puya.awst_build.eb.arc4.base import (
    ARC4TypeBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.awst_build.eb.string import StringExpressionBuilder as NativeStringExpressionBuilder
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class StringTypeBuilder(ARC4TypeBuilder, LiteralConverter):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4StringType, location)

    @typing.override
    @property
    def convertable_literal_types(self) -> Collection[pytypes.PyType]:
        return (pytypes.StrLiteralType,)

    @typing.override
    def convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder:
        return self.call([literal], [mypy.nodes.ARG_POS], [None], location)  # TODO: fixme

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            return StringExpressionBuilder(_arc4_encode_str_literal("", location))
        if len(args) == 1:
            return StringExpressionBuilder(_expect_string_or_bytes(args[0], location))
        raise CodeError("Invalid/unhandled arguments", location)


def _arc4_encode_str_literal(value: str, location: SourceLocation) -> Expression:
    return ARC4Encode(
        value=StringConstant(value=value, source_location=location),
        wtype=wtypes.arc4_string_alias,
        source_location=location,
    )


def _expect_string_or_bytes(expr: NodeBuilder, location: SourceLocation) -> Expression:
    expr = require_instance_builder(expr)
    match expr:
        case LiteralBuilder(value=str(string_literal)):
            return _arc4_encode_str_literal(string_literal, location)
        case LiteralBuilder(value=invalid_value, source_location=invalid_literal_location):
            raise CodeError(
                f"Can't construct {pytypes.ARC4StringType} from Python literal {invalid_value!r}",
                invalid_literal_location,
            )
        case InstanceBuilder(pytype=pytypes.ARC4StringType) as eb:
            return eb.resolve()
        case InstanceBuilder(pytype=pytypes.StringType) as eb:
            bytes_expr = eb.resolve()
            return ARC4Encode(
                value=bytes_expr, wtype=wtypes.arc4_string_alias, source_location=location
            )
        case InstanceBuilder(pytype=invalid_pytype, source_location=invalid_builder_location):
            raise CodeError(
                f"Can't construct {pytypes.ARC4StringType} from {invalid_pytype}",
                invalid_builder_location,
            )
        case _:
            typing.assert_never(expr)


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
                        other=_expect_string_or_bytes(rhs, rhs.source_location),
                        source_location=location,
                        wtype=wtypes.arc4_string_alias,
                    )
                )
            case _:
                return super().augmented_assignment(op, rhs, location)  # TODO: bad error message

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
                rhs = _expect_string_or_bytes(other, other.source_location)
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
            case LiteralBuilder(value=str(string_literal), source_location=literal_location):
                lhs = self.resolve()
                rhs = _arc4_encode_str_literal(string_literal, literal_location)
            case InstanceBuilder(pytype=pytypes.ARC4StringType) as eb:
                lhs = self.resolve()
                rhs = eb.resolve()
            case InstanceBuilder(pytype=pytypes.StringType) as eb:
                lhs = _string_to_native(self, location)
                rhs = eb.resolve()
            case _:
                return NotImplemented

        return compare_expr_bytes(lhs=lhs, op=op, rhs=rhs, source_location=location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(self, false_bytes=b"\x00\x00", location=location, negate=negate)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                return NativeStringExpressionBuilder(_string_to_native(self, location))
            case _:
                return super().member_access(name, location)


def _string_to_native(builder: InstanceBuilder, location: SourceLocation) -> Expression:
    assert builder.pytype == pytypes.ARC4StringType
    return ARC4Decode(
        value=builder.resolve(),
        wtype=pytypes.StringType.wtype,
        source_location=location,
    )
