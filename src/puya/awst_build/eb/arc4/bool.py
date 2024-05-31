from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import ARC4Decode, ARC4Encode, BoolConstant, Expression
from puya.awst_build import pytypes
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._utils import compare_bytes, get_bytes_expr_builder
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.utils import expect_operand_type
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build.eb.interface import BuilderComparisonOp, InstanceBuilder, NodeBuilder
    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ARC4BoolClassExpressionBuilder(ARC4ClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4BoolType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case []:
                native_bool: Expression = BoolConstant(value=False, source_location=location)
            case [val]:
                native_bool = expect_operand_type(val, pytypes.BoolType).rvalue()
            case _:
                raise CodeError(
                    f"arc4.Bool expects exactly one parameter of type {pytypes.BoolType}"
                )
        wtype = self.produces().wtype
        assert isinstance(wtype, wtypes.ARC4Type)
        return ARC4BoolExpressionBuilder(
            ARC4Encode(value=native_bool, wtype=wtype, source_location=location)
        )


class ARC4BoolExpressionBuilder(NotIterableInstanceExpressionBuilder):
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
                    value=self.expr,
                    wtype=pytypes.BoolType.wtype,
                    source_location=location,
                )
                return BoolExpressionBuilder(result_expr)
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                return super().member_access(name, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return compare_bytes(lhs=self, op=op, rhs=other, source_location=location)
