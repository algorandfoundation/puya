from __future__ import annotations

import typing

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    Expression,
    IntegerConstant,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import (
    NotIterableInstanceExpressionBuilder,
)
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb.arc4.base import (
    ARC4TypeBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.awst_build.utils import construct_from_literal
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from puya.parse import SourceLocation

__all__ = [
    "UIntNTypeBuilder",
    "UIntNExpressionBuilder",
]

logger = log.get_logger(__name__)


class UIntNTypeBuilder(ARC4TypeBuilder, LiteralConverter):
    @typing.override
    @property
    def convertable_literal_types(self) -> Collection[pytypes.PyType]:
        return (pytypes.IntLiteralType,)

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
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4UIntN)
        match args:
            case []:
                expr: Expression = IntegerConstant(value=0, wtype=wtype, source_location=location)
            case [LiteralBuilder(value=int(int_value))]:
                expr = IntegerConstant(value=int_value, wtype=wtype, source_location=location)
            case [
                InstanceBuilder(
                    pytype=(pytypes.BoolType | pytypes.UInt64Type | pytypes.BigUIntType)
                ) as eb
            ]:
                expr = ARC4Encode(value=eb.resolve(), wtype=wtype, source_location=location)
            case _:
                raise CodeError(
                    "Invalid/unhandled arguments",
                    location,
                )
        return UIntNExpressionBuilder(expr, typ)


class UIntNExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.ARC4UIntNType],
    BytesBackedInstanceExpressionBuilder[pytypes.ARC4UIntNType],
):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ARC4UIntNType)
        super().__init__(typ, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                result_expr = ARC4Decode(
                    value=self.resolve(),
                    wtype=self.pytype.native_type.wtype,
                    source_location=location,
                )
                return builder_for_instance(self.pytype.native_type, result_expr)
            case _:
                return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self,
            false_bytes=b"\x00" * (self.pytype.bits // 8),
            location=location,
            negate=negate,
        )

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        if isinstance(other, LiteralBuilder):
            other = construct_from_literal(other, self.pytype)
        match other.pytype:
            case pytypes.BigUIntType:
                other_expr = other.resolve()
            case pytypes.UInt64Type | pytypes.BoolType:
                other_expr = intrinsic_factory.itob_as(
                    other.resolve(), wtypes.biguint_wtype, location
                )
            case pytypes.ARC4UIntNType():
                other_expr = ReinterpretCast(
                    expr=other.resolve(),
                    wtype=wtypes.biguint_wtype,
                    source_location=other.source_location,
                )
            case _:
                return NotImplemented
        cmp_expr = NumericComparisonExpression(
            operator=NumericComparison(op.value),
            lhs=ReinterpretCast(
                expr=self.resolve(),
                wtype=wtypes.biguint_wtype,
                source_location=self.source_location,
            ),
            rhs=other_expr,
            source_location=location,
        )
        return BoolExpressionBuilder(cmp_expr)
