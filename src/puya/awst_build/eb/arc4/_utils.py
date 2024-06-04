from __future__ import annotations

import re
import typing

import attrs

from puya import arc4_util, log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import Expression
from puya.awst_build import pytypes
from puya.awst_build.arc4_utils import arc4_encode
from puya.awst_build.eb.interface import LiteralBuilder, NodeBuilder
from puya.awst_build.utils import construct_from_literal, require_instance_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)
_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")


def expect_arc4_operand_pytype(
    literal_or_builder: NodeBuilder, target_type: pytypes.PyType
) -> awst_nodes.Expression:
    target_wtype = target_type.wtype
    if isinstance(literal_or_builder, LiteralBuilder):
        return construct_from_literal(literal_or_builder, target_type).resolve()

    expr = require_instance_builder(literal_or_builder).resolve()
    if wtypes.has_arc4_equivalent_type(expr.wtype):
        new_wtype = wtypes.avm_to_arc4_equivalent_type(expr.wtype)
        expr = arc4_encode(expr, new_wtype, literal_or_builder.source_location)

    if expr.wtype != target_wtype:
        raise CodeError(
            f"Expected type {target_type}, got type {literal_or_builder.pytype}",
            expr.source_location,
        )
    return expr


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


def get_arc4_args_and_signature(
    method_sig: str,
    native_args: Sequence[NodeBuilder],
    loc: SourceLocation,
) -> tuple[Sequence[Expression], ARC4Signature]:
    method_name, maybe_args, maybe_return_type = _parse_method_signature(method_sig, loc)
    arg_types = (
        [
            _implicit_literal_to_arc4_conversion(require_instance_builder(na).pytype)
            for na in native_args
        ]
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
        expect_arc4_operand_pytype(arg, pt) for arg, pt in zip(native_args, arg_types, strict=True)
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
