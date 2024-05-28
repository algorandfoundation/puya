from __future__ import annotations

import decimal
import typing

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import DecimalConstant, Expression, Literal
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import get_bytes_expr_builder
from puya.awst_build.eb.arc4.base import ARC4ClassExpressionBuilder, arc4_bool_bytes
from puya.awst_build.eb.base import ExpressionBuilder, ValueExpressionBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation

if typing.TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = [
    "UFixedNxMClassExpressionBuilder",
    "UFixedNxMExpressionBuilder",
]


class UFixedNxMClassExpressionBuilder(ARC4ClassExpressionBuilder):
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
        fixed_wtype = typ.wtype
        assert isinstance(fixed_wtype, wtypes.ARC4UFixedNxM)
        loc = location
        match args:
            case []:
                literal_value = "0.0"
            case [Literal(value=str(literal_value))]:
                pass
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        with decimal.localcontext(
            decimal.Context(
                prec=160,
                traps=[
                    decimal.Rounded,
                    decimal.InvalidOperation,
                    decimal.Overflow,
                    decimal.DivisionByZero,
                ],
            )
        ):
            try:
                d = decimal.Decimal(literal_value)
            except ArithmeticError as ex:
                raise CodeError(f"Invalid decimal literal: {literal_value}", loc) from ex
            if d < 0:
                raise CodeError("Negative numbers not allowed", loc)
            try:
                q = d.quantize(decimal.Decimal(f"1e-{fixed_wtype.m}"))
            except ArithmeticError as ex:
                raise CodeError(f"Too many decimals, expected max of {fixed_wtype.m}", loc) from ex
        result = DecimalConstant(value=q, wtype=fixed_wtype, source_location=loc)
        return UFixedNxMExpressionBuilder(result, typ)


class UFixedNxMExpressionBuilder(ValueExpressionBuilder[pytypes.ARC4UFixedNxMType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ARC4UFixedNxMType)
        assert typ.generic in (
            pytypes.GenericARC4UFixedNxMType,
            pytypes.GenericARC4BigUFixedNxMType,
        )
        super().__init__(typ, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(
            self.expr,
            false_bytes=b"\x00" * (self.pytype.bits // 8),
            location=location,
            negate=negate,
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                return super().member_access(name, location)
