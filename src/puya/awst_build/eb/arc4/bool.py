import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import ARC4Decode, ARC4Encode, BoolConstant, Expression
from puya.awst_build import pytypes
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb._utils import compare_bytes
from puya.awst_build.eb.arc4.base import ARC4TypeBuilder, arc4_bool_bytes
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puya.errors import CodeError
from puya.parse import SourceLocation

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
                    ARC4Encode(
                        value=BoolConstant(value=bool_literal, source_location=location),
                        wtype=self._arc4_wtype,
                        source_location=location,
                    )
                )
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
            case []:
                native_bool: Expression = BoolConstant(value=False, source_location=location)
            case [InstanceBuilder(pytype=pytypes.BoolType) as eb]:
                native_bool = eb.resolve()
            case _:
                raise CodeError(
                    f"arc4.Bool expects exactly one parameter of type {pytypes.BoolType}"
                )
        return ARC4BoolExpressionBuilder(
            ARC4Encode(value=native_bool, wtype=self._arc4_wtype, source_location=location)
        )

    @property
    def _arc4_wtype(self) -> wtypes.ARC4Type:
        wtype = self.produces().wtype
        assert isinstance(wtype, wtypes.ARC4Type)
        return wtype


class ARC4BoolExpressionBuilder(
    NotIterableInstanceExpressionBuilder, BytesBackedInstanceExpressionBuilder
):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.ARC4BoolType, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(self, false_bytes=b"\x00", location=location, negate=negate)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                result_expr: Expression = ARC4Decode(
                    value=self.resolve(),
                    wtype=pytypes.BoolType.wtype,
                    source_location=location,
                )
                return BoolExpressionBuilder(result_expr)
            case _:
                return super().member_access(name, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        # TODO(first): support comparisons with native bool
        return compare_bytes(lhs=self, op=op, rhs=other, source_location=location)
