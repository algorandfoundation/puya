import re
import typing

import attrs

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.arc4_utils import pytype_to_arc4_pytype, split_tuple_types
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.utils import maybe_resolve_literal

logger = log.get_logger(__name__)

_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")
_ARRAY_PATTERN = re.compile(r"^\[[0-9]*]$")


@attrs.frozen(kw_only=True)
class ParsedARC4SignatureString:
    value: str
    name: str
    maybe_args: tuple[str, ...] | None
    maybe_returns: str | None


def split_arc4_signature(method: NodeBuilder) -> ParsedARC4SignatureString:
    method_sig = expect.simple_string_literal(method, default=expect.default_raise)
    method_name, maybe_args_str, maybe_returns = _split_signature(
        method_sig, method.source_location
    )
    if maybe_args_str is None:
        maybe_args = None
    elif maybe_args_str:
        maybe_args = tuple(split_tuple_types(maybe_args_str))
    else:
        maybe_args = ()
    return ParsedARC4SignatureString(
        value=method_sig, name=method_name, maybe_args=maybe_args, maybe_returns=maybe_returns
    )


def implicit_arc4_type_arg_conversion(typ: pytypes.PyType, loc: SourceLocation) -> pytypes.PyType:
    match typ:
        case pytypes.StrLiteralType:
            return pytypes.ARC4StringType
        case pytypes.BytesLiteralType:
            return pytypes.ARC4DynamicBytesType
        case pytypes.IntLiteralType:
            return pytypes.ARC4UIntN_Aliases[64]
        # convert an inner txn type to the equivalent group txn type
        case pytypes.InnerTransactionFieldsetType(transaction_type=txn_type):
            return pytypes.GroupTransactionTypes[txn_type]

    def on_error(invalid_pytype: pytypes.PyType, loc_: SourceLocation | None) -> typing.Never:
        raise CodeError(
            f"{invalid_pytype} is not an ARC-4 type and no implicit ARC-4 conversion possible",
            loc_,
        )

    return pytype_to_arc4_pytype(typ, on_error, encode_resource_types=False, source_location=loc)


def implicit_arc4_conversion(operand: NodeBuilder, target_type: pytypes.PyType) -> InstanceBuilder:
    instance = expect.instance_builder(operand, default=expect.default_dummy_value(target_type))
    instance = _maybe_resolve_arc4_literal(instance, target_type)
    if target_type <= instance.pytype:
        return instance

    target_wtype = target_type.wtype
    if not isinstance(target_wtype, wtypes.ARC4Type):
        raise InternalError(
            "implicit_arc4_conversion expected target_type to be an ARC-4 type,"
            f" got {target_type}",
            instance.source_location,
        )
    instance_wtype = instance.pytype.checked_wtype(instance.source_location)
    if instance_wtype == target_wtype:
        return instance

    if isinstance(instance_wtype, wtypes.ARC4Type):
        # if it's already an ARC-4 type and encoding fails, it's an incompatible value
        error_message = f"expected type {target_type}, got type {instance.pytype}"
    else:
        error_message = f"cannot encode {instance.pytype} to {target_type}"
    encoded = awst_nodes.ARC4Encode(
        value=instance.resolve(),
        wtype=target_wtype,
        error_message=error_message,
        source_location=instance.source_location,
    )
    return builder_for_instance(target_type, encoded)


def _maybe_resolve_arc4_literal(
    operand: InstanceBuilder, target_type: pytypes.PyType
) -> InstanceBuilder:
    """Handles special case of resolving a literal tuple into an arc4 tuple"""
    from puyapy.awst_build.eb.tuple import TupleLiteralBuilder

    if isinstance(operand, TupleLiteralBuilder) and isinstance(target_type, pytypes.ARC4TupleType):
        resolved_items = [
            _maybe_resolve_arc4_literal(item, item_type)
            for item, item_type in zip(operand.iterate_static(), target_type.items, strict=True)
        ]
        return TupleLiteralBuilder(resolved_items, operand.source_location)
    return maybe_resolve_literal(operand, target_type)


def _split_signature(
    signature: str, location: SourceLocation
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
            if returns is not None and _ARRAY_PATTERN.match(remaining):
                returns += remaining
            elif not name:
                name = remaining
            elif args is None:
                raise CodeError(
                    f"invalid signature, args not well defined: {name=}, {remaining=}", location
                )
            elif returns:
                raise CodeError(
                    f"invalid signature, text after returns:"
                    f" {name=}, {args=}, {returns=}, {remaining=}",
                    location,
                )
            else:
                returns = remaining
    if not name or not _VALID_NAME_PATTERN.match(name):
        logger.error(f"invalid signature: {name=}", location=location)
    return name, args, returns
