import re
import typing
from collections.abc import Sequence

import attrs
import mypy.nodes

from puya import arc4_util, log
from puya.awst import (
    nodes as awst_nodes,
)
from puya.awst_build import arc4_utils, pytypes
from puya.awst_build.arc4_utils import pytype_to_arc4_pytype
from puya.awst_build.eb.factories import builder_for_type
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.utils import maybe_resolve_literal, require_instance_builder
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)

_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")


def implicit_arc4_conversion(operand: NodeBuilder, target_type: pytypes.PyType) -> InstanceBuilder:
    from puya.awst.wtypes import ARC4Type

    operand = require_instance_builder(operand)
    operand = maybe_resolve_literal(operand, target_type)
    if operand.pytype == target_type:
        return operand
    target_wtype = target_type.wtype
    if not isinstance(target_wtype, ARC4Type):
        raise InternalError(
            "implicit_operand_conversion expected target_type to be an ARC-4 type,"
            f" got {target_type}",
            operand.source_location,
        )
    if isinstance(operand.pytype.wtype, ARC4Type):
        raise CodeError(
            f"expected type {target_type}, got type {operand.pytype}", operand.source_location
        )
    if operand.pytype.wtype not in target_wtype.encodeable_types:
        raise CodeError(
            f"cannot encode {operand.pytype} to {target_type}", operand.source_location
        )
    target_type_builder = builder_for_type(target_type, operand.source_location)
    return target_type_builder.call(
        args=[operand],
        arg_names=[None],
        arg_kinds=[mypy.nodes.ARG_POS],
        location=operand.source_location,
    )


@attrs.frozen
class ARC4Signature:
    method_name: str
    arg_types: Sequence[pytypes.PyType] = attrs.field(converter=tuple[pytypes.PyType, ...])
    return_type: pytypes.PyType | None

    @property
    def method_selector(self) -> str:
        args = ",".join(map(arc4_utils.pytype_to_arc4, self.arg_types))
        return_type = self.return_type or pytypes.NoneType
        return f"{self.method_name}({args}){arc4_utils.pytype_to_arc4(return_type)}"


def get_arc4_args_and_signature(
    method_sig: str,
    native_args: Sequence[InstanceBuilder],
    loc: SourceLocation,
) -> tuple[list[InstanceBuilder], ARC4Signature]:
    method_name, arg_types, return_type = _parse_method_signature(method_sig, loc)
    if arg_types is None:
        arg_types = [_implicit_arc4_type_conversion(na.pytype, loc) for na in native_args]
    else:
        num_args = len(native_args)
        sig_num_args = len(arg_types)
        if sig_num_args != num_args:
            raise CodeError(
                f"number of arguments ({num_args}) does not match signature ({sig_num_args})", loc
            )

    arc4_args = [
        implicit_arc4_conversion(arg, pt) for arg, pt in zip(native_args, arg_types, strict=True)
    ]
    return arc4_args, ARC4Signature(method_name, arg_types, return_type)


def _implicit_arc4_type_conversion(typ: pytypes.PyType, loc: SourceLocation) -> pytypes.PyType:
    match typ:
        case pytypes.StrLiteralType:
            return pytypes.ARC4StringType
        case pytypes.BytesLiteralType:
            return pytypes.ARC4DynamicBytesType
        case pytypes.IntLiteralType:
            return pytypes.ARC4UIntN_Aliases[64]

    def on_error(invalid_pytype: pytypes.PyType) -> typing.Never:
        raise CodeError(
            f"{invalid_pytype} is not an ARC4 type and no implicit ARC4 conversion possible",
            loc,
        )

    return pytype_to_arc4_pytype(typ, on_error)


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
    args = (
        [arc4_utils.arc4_to_pytype(a, location) for a in arc4_util.split_tuple_types(maybe_args)]
        if maybe_args
        else None
    )
    returns = arc4_utils.arc4_to_pytype(maybe_returns, location) if maybe_returns else None
    return name, args, returns
