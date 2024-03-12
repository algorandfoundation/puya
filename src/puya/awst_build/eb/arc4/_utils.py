from __future__ import annotations

import decimal
import typing
from typing import TYPE_CHECKING

import structlog

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import DecimalConstant
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.utils import convert_literal
from puya.errors import CodeError

if TYPE_CHECKING:
    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


def convert_arc4_literal(
    literal: awst_nodes.Literal,
    target_wtype: wtypes.ARC4Type,
    loc: SourceLocation | None = None,
) -> awst_nodes.Expression:
    literal_value: typing.Any = literal.value
    loc = loc or literal.source_location
    match target_wtype:
        case wtypes.ARC4UIntN():
            return awst_nodes.IntegerConstant(
                value=literal_value, wtype=target_wtype, source_location=loc
            )
        case wtypes.ARC4UFixedNxM() as fixed_wtype:
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
                    raise CodeError(
                        f"Too many decimals, expected max of {fixed_wtype.m}", loc
                    ) from ex
            return DecimalConstant(
                source_location=loc,
                value=q,
                wtype=fixed_wtype,
            )
        case wtypes.arc4_dynamic_bytes:
            return awst_nodes.ARC4Encode(
                value=awst_nodes.BytesConstant(
                    value=literal_value,
                    source_location=loc,
                    encoding=awst_nodes.BytesEncoding.unknown,
                ),
                source_location=loc,
                wtype=target_wtype,
            )
        case wtypes.arc4_string_wtype:
            if isinstance(literal_value, str):
                try:
                    literal_bytes = literal_value.encode("utf8")
                except ValueError:
                    pass
                else:
                    return awst_nodes.ARC4Encode(
                        value=awst_nodes.BytesConstant(
                            value=literal_bytes,
                            source_location=loc,
                            encoding=awst_nodes.BytesEncoding.utf8,
                        ),
                        source_location=loc,
                        wtype=target_wtype,
                    )
        case wtypes.arc4_bool_wtype:
            return awst_nodes.ARC4Encode(
                value=awst_nodes.BoolConstant(
                    value=literal_value,
                    source_location=loc,
                ),
                source_location=loc,
                wtype=target_wtype,
            )
    raise CodeError(f"Can't construct {target_wtype} from Python literal {literal_value}", loc)


def expect_arc4_operand_wtype(
    literal_or_expr: awst_nodes.Literal | awst_nodes.Expression | ExpressionBuilder,
    target_wtype: wtypes.WType,
) -> awst_nodes.Expression:
    if isinstance(literal_or_expr, awst_nodes.Literal):
        if isinstance(target_wtype, wtypes.ARC4Type):
            return convert_arc4_literal(literal_or_expr, target_wtype)
        return convert_literal(literal_or_expr, target_wtype)
    if isinstance(literal_or_expr, ExpressionBuilder):
        literal_or_expr = literal_or_expr.rvalue()

    if literal_or_expr.wtype != target_wtype:
        raise CodeError(
            f"Expected type {target_wtype}, got type {literal_or_expr.wtype}",
            literal_or_expr.source_location,
        )
    return literal_or_expr
