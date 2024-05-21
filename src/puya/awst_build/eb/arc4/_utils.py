from __future__ import annotations

import decimal
import re
import typing

import attrs

from puya import arc4_util, log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import DecimalConstant, Expression, Literal
from puya.awst_build.arc4_utils import arc4_encode
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.utils import convert_literal
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)
_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")


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

    if wtypes.has_arc4_equivalent_type(literal_or_expr.wtype):
        new_wtype = wtypes.avm_to_arc4_equivalent_type(literal_or_expr.wtype)
        literal_or_expr = arc4_encode(literal_or_expr, new_wtype, literal_or_expr.source_location)

    if literal_or_expr.wtype != target_wtype:
        raise CodeError(
            f"Expected type {target_wtype}, got type {literal_or_expr.wtype}",
            literal_or_expr.source_location,
        )
    return literal_or_expr


@attrs.frozen
class ARC4Signature:
    method_name: str
    arg_types: list[wtypes.WType]
    return_type: wtypes.WType | None

    @property
    def method_selector(self) -> str:
        args = ",".join(map(arc4_util.wtype_to_arc4, self.arg_types))
        return_type = self.return_type or wtypes.void_wtype
        return f"{self.method_name}({args}){arc4_util.wtype_to_arc4(return_type)}"


def get_arc4_args_and_signature(
    method_sig: str, native_args: Sequence[ExpressionBuilder | Literal], loc: SourceLocation
) -> tuple[Sequence[Expression], ARC4Signature]:
    method_name, maybe_args, maybe_return_type = _parse_method_signature(method_sig, loc)
    arg_types = list(map(_arg_to_arc4_wtype, native_args)) if maybe_args is None else maybe_args
    num_args = len(native_args)
    num_types = len(arg_types)
    if num_types != num_args:
        raise CodeError(
            f"Number of arguments ({num_args}) does not match signature ({num_types})", loc
        )

    arc4_args = [
        expect_arc4_operand_wtype(arg, wtype)
        for arg, wtype in zip(native_args, arg_types, strict=True)
    ]
    arc4_types = [a.wtype for a in arc4_args]
    return arc4_args, ARC4Signature(method_name, arc4_types, maybe_return_type)


def _arg_to_arc4_wtype(
    arg: ExpressionBuilder | Literal, wtype: wtypes.WType | None = None
) -> wtypes.WType:
    # if wtype is known, then ensure arg can be coerced to that type
    if wtype:
        return expect_arc4_operand_wtype(arg, wtype).wtype
    # otherwise infer arg from literal type
    match arg:
        case ExpressionBuilder(value_type=wtypes.WType() as expr_wtype):
            return expr_wtype
        case Literal(value=bytes()):
            return wtypes.arc4_dynamic_bytes
        case Literal(value=int()):
            return wtypes.ARC4UIntN.from_scale(64)
        case Literal(value=str()):
            return wtypes.arc4_string_wtype
        case Literal(value=bool()):
            return wtypes.arc4_bool_wtype
    raise CodeError("Invalid arg type", arg.source_location)


def arc4_tuple_from_items(
    items: Sequence[awst_nodes.Expression], source_location: SourceLocation
) -> awst_nodes.ARC4Encode:
    args_tuple = awst_nodes.TupleExpression.from_items(items, source_location)
    return awst_nodes.ARC4Encode(
        value=args_tuple,
        wtype=arc4_util.make_tuple_wtype(args_tuple.wtype.types, source_location),
        source_location=source_location,
    )


def _split_signature(
    signature: str, location: SourceLocation | None
) -> tuple[str, str | None, str | None]:
    """Splits signature into name, args and returns"""
    level = 0
    last_idx = 0
    name: str = ""
    args: str | None = None
    returns: str | None = None
    for idx, tok in enumerate(signature):
        if tok == "(":
            level += 1
            if level == 1:
                if not name:
                    name = signature[:idx]
                last_idx = idx + 1
        elif tok == ")":
            level -= 1
            if level == 0:
                if args is None:
                    args = signature[last_idx:idx]
                elif returns is None:
                    returns = signature[last_idx - 1 : idx + 1]
                last_idx = idx + 1
    if last_idx < len(signature):
        remaining = signature[last_idx:]
        if remaining:
            if not name:
                name = remaining
            elif not args:
                raise CodeError(
                    f"Invalid signature, args not well defined: {name=}, {remaining=}",
                    location,
                )
            elif returns:
                raise CodeError(
                    f"Invalid signature, text after returns:"
                    f" {name=}, {args=}, {returns=}, {remaining=}",
                    location,
                )
            else:
                returns = remaining
    if not name or not _VALID_NAME_PATTERN.match(name):
        raise CodeError(f"Invalid signature: {name=}", location)
    return name, args, returns


def _parse_method_signature(
    signature: str, location: SourceLocation
) -> tuple[str, list[wtypes.WType] | None, wtypes.WType | None]:
    name, maybe_args, maybe_returns = _split_signature(signature, location)
    args: list[wtypes.WType] | None = None
    returns: wtypes.WType | None = None
    if maybe_args:
        args = [
            arc4_util.arc4_to_wtype(a, location) for a in arc4_util.split_tuple_types(maybe_args)
        ]
    if maybe_returns:
        returns = arc4_util.arc4_to_wtype(maybe_returns, location)
    return name, args, returns
