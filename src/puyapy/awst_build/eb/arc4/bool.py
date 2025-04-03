import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import ARC4Decode, ARC4Encode, BoolConstant, Expression
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puyapy.awst_build.eb._utils import compare_bytes
from puyapy.awst_build.eb.arc4._base import ARC4TypeBuilder, arc4_bool_bytes
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)

logger = log.get_logger(__name__)


class ARC4BoolTypeBuilder(ARC4TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4BoolType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case bool(bool_literal):
                return ARC4BoolExpressionBuilder(
                    BoolConstant(
                        value=bool_literal, source_location=location, wtype=wtypes.arc4_bool_wtype
                    ),
                )
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
            case None:
                expr: Expression = BoolConstant(
                    value=False, source_location=location, wtype=wtypes.arc4_bool_wtype
                )
            case _:
                arg = expect.argument_of_type_else_dummy(arg, pytypes.BoolType)
                native_bool = arg.resolve()
                expr = ARC4Encode(
                    value=native_bool, wtype=wtypes.arc4_bool_wtype, source_location=location
                )
        return ARC4BoolExpressionBuilder(expr)


class ARC4BoolExpressionBuilder(
    NotIterableInstanceExpressionBuilder, BytesBackedInstanceExpressionBuilder
):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.ARC4BoolType, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self,
            false_bytes=b"\x00",
            negate=negate,
            location=location,
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                return self._native(location)
            case _:
                return super().member_access(name, location)

    def _native(self, location: SourceLocation) -> BoolExpressionBuilder:
        result_expr: Expression = ARC4Decode(
            value=self.resolve(),
            wtype=pytypes.BoolType.wtype,
            source_location=location,
        )
        return BoolExpressionBuilder(result_expr)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        if other.pytype == pytypes.BoolType:
            lhs = self._native(self.source_location)
            return lhs.compare(other, op, location)
        return compare_bytes(self=self, op=op, other=other, source_location=location)
