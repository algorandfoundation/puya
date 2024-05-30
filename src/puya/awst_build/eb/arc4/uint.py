from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Decode,
    ARC4Encode,
    Expression,
    IntegerConstant,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._utils import get_bytes_expr_builder
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    InstanceBuilder,
    NodeBuilder,
    NotIterableInstanceExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.utils import construct_from_literal
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

__all__ = [
    "UIntNClassExpressionBuilder",
    "UIntNExpressionBuilder",
]

logger = log.get_logger(__name__)


class UIntNClassExpressionBuilder(ARC4ClassExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4UIntN)
        match args:
            case []:
                expr: Expression = IntegerConstant(value=0, wtype=wtype, source_location=location)
            case [Literal(value=int(int_value))]:
                expr = IntegerConstant(value=int_value, wtype=wtype, source_location=location)
            case [
                NodeBuilder(
                    pytype=(pytypes.BoolType | pytypes.UInt64Type | pytypes.BigUIntType)
                ) as eb
            ]:
                expr = ARC4Encode(value=eb.rvalue(), wtype=wtype, source_location=location)
            case _:
                raise CodeError(
                    "Invalid/unhandled arguments",
                    location,
                )
        return UIntNExpressionBuilder(expr, typ)


class UIntNExpressionBuilder(NotIterableInstanceExpressionBuilder[pytypes.ARC4UIntNType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ARC4UIntNType)
        super().__init__(typ, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "native":
                result_expr = ARC4Decode(
                    value=self.expr,
                    wtype=self.pytype.native_type.wtype,
                    source_location=location,
                )
                return builder_for_instance(self.pytype.native_type, result_expr)
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self.expr,
            false_bytes=b"\x00" * (self.pytype.bits // 8),
            location=location,
            negate=negate,
        )

    @typing.override
    def compare(
        self, other: NodeBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> NodeBuilder:
        if isinstance(other, Literal):
            other = construct_from_literal(other, self.pytype)
        match other.pytype:
            case pytypes.BigUIntType:
                other_expr = other.rvalue()
            case pytypes.UInt64Type | pytypes.BoolType:
                other_expr = intrinsic_factory.itob_as(
                    other.rvalue(), wtypes.biguint_wtype, location
                )
            case pytypes.ARC4UIntNType():
                other_expr = ReinterpretCast(
                    expr=other.rvalue(),
                    wtype=wtypes.biguint_wtype,
                    source_location=other.source_location,
                )
            case _:
                return NotImplemented
        cmp_expr = NumericComparisonExpression(
            operator=NumericComparison(op.value),
            lhs=ReinterpretCast(
                expr=self.expr,
                wtype=wtypes.biguint_wtype,
                source_location=self.source_location,
            ),
            rhs=other_expr,
            source_location=location,
        )
        return BoolExpressionBuilder(cmp_expr)
