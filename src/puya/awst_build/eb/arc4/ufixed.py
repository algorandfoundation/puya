import decimal
import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import DecimalConstant, Expression
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedInstanceExpressionBuilder
from puya.awst_build.eb._utils import compare_bytes
from puya.awst_build.eb.arc4._base import ARC4TypeBuilder, arc4_bool_bytes
from puya.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puya.parse import SourceLocation

__all__ = [
    "UFixedNxMTypeBuilder",
    "UFixedNxMExpressionBuilder",
]

logger = log.get_logger(__name__)


class UFixedNxMTypeBuilder(ARC4TypeBuilder):
    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case str(literal_value):
                result = self._str_to_decimal_constant(
                    literal_value, error_location=literal.source_location, location=location
                )
                return UFixedNxMExpressionBuilder(result, self.produces())
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        if arg is None:
            result = self._str_to_decimal_constant("0.0", location=location)
            return UFixedNxMExpressionBuilder(result, self.produces())

        arg = expect.argument_of_type(arg, pytypes.StrLiteralType, default=expect.default_raise)
        return arg.resolve_literal(UFixedNxMTypeBuilder(self.produces(), location))

    def _str_to_decimal_constant(
        self,
        literal_value: str,
        *,
        location: SourceLocation,
        error_location: SourceLocation | None = None,
    ) -> DecimalConstant:
        error_location = location or error_location
        fixed_wtype = self.produces().wtype
        assert isinstance(fixed_wtype, wtypes.ARC4UFixedNxM)

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
            except ArithmeticError:
                logger.error("invalid decimal literal", location=error_location)  # noqa: TRY400
                d = decimal.Decimal()
            try:
                q = d.quantize(decimal.Decimal(f"1e-{fixed_wtype.m}"))
            except ArithmeticError:
                logger.error(  # noqa: TRY400
                    "invalid decimal constant (wrong precision)", location=error_location
                )
                q = decimal.Decimal("0." + "0" * fixed_wtype.m)

            sign, digits, exponent = q.as_tuple()
            if sign != 0:  # is negative
                logger.error(
                    "invalid decimal constant (value is negative)", location=error_location
                )
            if not isinstance(exponent, int):  # is infinite
                logger.error(
                    "invalid decimal constant (value is infinite)", location=error_location
                )
            adjusted_int = int("".join(map(str, digits)))
            if adjusted_int.bit_length() > fixed_wtype.n:
                logger.error("invalid decimal constant (too many bits)", location=error_location)
            result = DecimalConstant(value=q, wtype=fixed_wtype, source_location=location)
            return result


class UFixedNxMExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.ARC4UFixedNxMType],
    BytesBackedInstanceExpressionBuilder[pytypes.ARC4UFixedNxMType],
):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ARC4UFixedNxMType)
        assert typ.generic in (
            pytypes.GenericARC4UFixedNxMType,
            pytypes.GenericARC4BigUFixedNxMType,
        )
        super().__init__(typ, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self,
            false_bytes=b"\x00" * (self.pytype.bits // 8),
            negate=negate,
            location=location,
        )

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.resolve_literal(UFixedNxMTypeBuilder(self.pytype, other.source_location))
        return compare_bytes(op=op, lhs=self, rhs=other, source_location=location)
