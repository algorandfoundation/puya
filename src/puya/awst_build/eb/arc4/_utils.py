from __future__ import annotations

import decimal
import re
import typing

import attrs
import mypy.nodes
import mypy.types

from puya import arc4_util, log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import DecimalConstant, Expression, Literal
from puya.awst_build import constants, pytypes
from puya.awst_build.arc4_utils import arc4_encode, get_arc4_method_config, get_func_types
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.utils import convert_literal, get_decorators_by_fullname
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from puya.awst_build.context import ASTConversionModuleContext
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

    if wtypes.has_arc4_equivalent_type(target_wtype):
        target_wtype = wtypes.avm_to_arc4_equivalent_type(target_wtype)
        literal_or_expr = arc4_encode(
            literal_or_expr, target_wtype, literal_or_expr.source_location
        )

    if literal_or_expr.wtype != target_wtype:
        raise CodeError(
            f"Expected type {target_wtype}, got type {literal_or_expr.wtype}",
            literal_or_expr.source_location,
        )
    return literal_or_expr


@attrs.frozen
class ARC4Signature:
    method_name: str
    arg_types: Sequence[pytypes.PyType] = attrs.field(converter=tuple[pytypes.PyType, ...])
    return_type: pytypes.PyType | None

    @property
    def method_selector(self) -> str:
        args = ",".join(map(arc4_util.pytype_to_arc4, self.arg_types))
        return_type = self.return_type or pytypes.NoneType
        return f"{self.method_name}({args}){arc4_util.pytype_to_arc4(return_type)}"


def get_arc4_signature(
    context: ASTConversionModuleContext,
    type_info: mypy.nodes.TypeInfo,
    member_name: str,
    location: SourceLocation,
) -> ARC4Signature:
    dec = type_info.get_method(member_name)
    if isinstance(dec, mypy.nodes.Decorator):
        decorators = get_decorators_by_fullname(context, dec)
        abimethod_dec = decorators.get(constants.ABIMETHOD_DECORATOR)
        if abimethod_dec is not None:
            func_def = dec.func
            arc4_method_config = get_arc4_method_config(context, abimethod_dec, func_def)
            *arg_types, return_type = get_func_types(context, func_def, location).values()
            return ARC4Signature(arc4_method_config.name, arg_types, return_type)
    raise CodeError(f"'{type_info.fullname}.{member_name}' is not a valid ARC4 method", location)


def get_arc4_args_and_signature(
    method_sig: str,
    arg_typs: Sequence[pytypes.PyType],
    native_args: Sequence[ExpressionBuilder | Literal],
    loc: SourceLocation,
) -> tuple[Sequence[Expression], ARC4Signature]:
    method_name, maybe_args, maybe_return_type = _parse_method_signature(method_sig, loc)
    arg_types = (
        list(map(_implicit_literal_to_arc4_conversion, arg_typs))
        if maybe_args is None
        else maybe_args
    )
    num_args = len(native_args)
    num_types = len(arg_types)
    if num_types != num_args:
        raise CodeError(
            f"Number of arguments ({num_args}) does not match signature ({num_types})", loc
        )

    arc4_args = [
        expect_arc4_operand_wtype(arg, pt.wtype)
        for arg, pt in zip(native_args, arg_types, strict=True)
    ]
    return arc4_args, ARC4Signature(method_name, arg_types, maybe_return_type)


def _implicit_literal_to_arc4_conversion(typ: pytypes.PyType) -> pytypes.PyType:
    # infer arg from literal type
    match typ:
        case pytypes.StrLiteralType:
            return pytypes.ARC4StringType
        case pytypes.BoolType:
            return pytypes.ARC4BoolType
        case pytypes.BytesLiteralType:
            return pytypes.ARC4DynamicBytesType
        case pytypes.IntLiteralType:
            return pytypes.ARC4UIntN_Aliases[64]
        case _:
            return typ


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
) -> tuple[str, list[pytypes.PyType] | None, pytypes.PyType | None]:
    name, maybe_args, maybe_returns = _split_signature(signature, location)
    args: list[pytypes.PyType] | None = None
    returns: pytypes.PyType | None = None
    if maybe_args:
        args = [
            arc4_util.arc4_to_pytype(a, location) for a in arc4_util.split_tuple_types(maybe_args)
        ]
    if maybe_returns:
        returns = arc4_util.arc4_to_pytype(maybe_returns, location)
    return name, args, returns
