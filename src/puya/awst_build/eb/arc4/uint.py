from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    Expression,
    IntegerConstant,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import uint64_to_biguint
from puya.awst_build.eb.arc4._utils import convert_arc4_literal
from puya.awst_build.eb.arc4.base import (
    ARC4ClassExpressionBuilder,
    ARC4EncodedExpressionBuilder,
    arc4_bool_bytes,
)
from puya.awst_build.eb.base import BuilderComparisonOp, ExpressionBuilder
from puya.awst_build.eb.bool import BoolExpressionBuilder
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
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        typ = self.produces2()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4UFixedNxM)
        match args:
            case []:
                expr: Expression = IntegerConstant(value=0, wtype=wtype, source_location=location)
            case [Literal(value=int(int_value))]:
                expr = IntegerConstant(value=int_value, wtype=wtype, source_location=location)
            case [
                ExpressionBuilder(
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


class UIntNExpressionBuilder(ARC4EncodedExpressionBuilder[pytypes.ARC4UIntNType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ARC4UIntNType)
        if typ == pytypes.ARC4ByteType or typ.generic == pytypes.GenericARC4UIntNType:
            native_pytype = pytypes.UInt64Type
        else:
            assert typ.generic == pytypes.GenericARC4BigUIntNType
            native_pytype = pytypes.BigUIntType
        super().__init__(typ, expr, native_pytype=native_pytype)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(
            self.expr,
            false_bytes=b"\x00" * (self.pytype.bits // 8),
            location=location,
            negate=negate,
        )

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        if isinstance(other, Literal):
            other_expr = convert_arc4_literal(other, self.pytype)
        else:
            other_expr = other.rvalue()
        match other_expr.wtype:
            case wtypes.biguint_wtype:
                pass
            case wtypes.ARC4UIntN():
                other_expr = ReinterpretCast(
                    expr=other_expr,
                    wtype=wtypes.biguint_wtype,
                    source_location=other_expr.source_location,
                )
            case wtypes.uint64_wtype:
                other_expr = uint64_to_biguint(other, location)
            case _:
                return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=ReinterpretCast(
                expr=self.expr,
                wtype=wtypes.biguint_wtype,
                source_location=self.source_location,
            ),
            operator=NumericComparison(op.value),
            rhs=other_expr,
        )
        return BoolExpressionBuilder(cmp_expr)
