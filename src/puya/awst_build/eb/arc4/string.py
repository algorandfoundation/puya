from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    ArrayConcat,
    ArrayExtend,
    BytesComparisonExpression,
    EqualityComparison,
    Expression,
    ExpressionStatement,
    Statement,
    StringConstant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import (
    NotIterableInstanceExpressionBuilder,
)
from puya.awst_build.eb._utils import get_bytes_expr, get_bytes_expr_builder
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puya.awst_build.eb.string import StringExpressionBuilder as NativeStringExpressionBuilder
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class StringClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4StringType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
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
        wtype=wtypes.arc4_string_wtype,
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
            return eb.rvalue()
        case InstanceBuilder(pytype=pytypes.StringType) as eb:
            bytes_expr = eb.rvalue()
            return ARC4Encode(
                value=bytes_expr, wtype=wtypes.arc4_string_wtype, source_location=location
            )
        case InstanceBuilder(pytype=invalid_pytype, source_location=invalid_builder_location):
            raise CodeError(
                f"Can't construct {pytypes.ARC4StringType} from {invalid_pytype}",
                invalid_builder_location,
            )
        case _:
            typing.assert_never(expr)


class StringExpressionBuilder(NotIterableInstanceExpressionBuilder):
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
                        base=self.expr,
                        other=_expect_string_or_bytes(rhs, rhs.source_location),
                        source_location=location,
                        wtype=wtypes.arc4_string_wtype,
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
                lhs = self.expr
                rhs = _expect_string_or_bytes(other, other.source_location)
                if reverse:
                    (lhs, rhs) = (rhs, lhs)
                return StringExpressionBuilder(
                    ArrayConcat(
                        left=lhs,
                        right=rhs,
                        source_location=location,
                        wtype=wtypes.arc4_string_wtype,
                    )
                )

            case _:
                return super().binary_op(other, op, location, reverse=reverse)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other_expr: Expression
        match other:
            case LiteralBuilder(value=str(string_literal), source_location=literal_location):
                other_expr = _arc4_encode_str_literal(string_literal, literal_location)
            case InstanceBuilder(pytype=pytypes.ARC4StringType) as eb:
                other_expr = eb.rvalue()
            case InstanceBuilder(pytype=pytypes.StringType):
                raise InternalError("need to implement this")  # TODO
            case _:
                return NotImplemented

        return BoolExpressionBuilder(
            BytesComparisonExpression(
                source_location=location,
                lhs=get_bytes_expr(self.expr),
                operator=EqualityComparison(op.value),
                rhs=get_bytes_expr(other_expr),
            )
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self.expr, false_bytes=b"\x00\x00", location=location, negate=negate
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                result_expr: Expression = ARC4Decode(
                    value=self.expr,
                    wtype=pytypes.StringType.wtype,
                    source_location=location,
                )
                return NativeStringExpressionBuilder(result_expr)
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                return super().member_access(name, location)
