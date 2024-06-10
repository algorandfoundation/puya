import re
from collections.abc import Iterable, Sequence
from itertools import zip_longest

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst_build import constants
from puya.errors import CodeError, InternalError
from puya.models import ARC4MethodConfig
from puya.parse import SourceLocation
from puya.utils import round_bits_to_nearest_bytes


def get_arc4_fixed_bit_size(wtype: wtypes.ARC4Type) -> int:
    if is_arc4_dynamic_size(wtype):
        raise InternalError(f"Cannot get fixed bit size for a dynamic ABI type: {wtype}")
    match wtype:
        case wtypes.arc4_bool_wtype:
            return 1
        case wtypes.ARC4UIntN(n=n) | wtypes.ARC4UFixedNxM(n=n):
            return n
        case wtypes.ARC4StaticArray(element_type=element_type, array_size=array_size):
            el_size = get_arc4_fixed_bit_size(element_type)
            return round_bits_to_nearest_bytes(array_size * el_size)
        case wtypes.ARC4Tuple(types=types) | wtypes.ARC4Struct(types=types):
            return determine_arc4_tuple_head_size(types, round_end_result=True)
    raise InternalError(f"Unexpected ABI wtype: {wtype}")


def is_arc4_dynamic_size(wtype: wtypes.ARC4Type) -> bool:
    match wtype:
        # TODO: make arc4_string_wtype an ARC4DynamicArray
        case wtypes.arc4_string_wtype | wtypes.ARC4DynamicArray():
            return True
        case wtypes.ARC4StaticArray(element_type=element_type):
            return is_arc4_dynamic_size(element_type)
        case wtypes.ARC4Tuple(types=types) | wtypes.ARC4Struct(types=types):
            return any(map(is_arc4_dynamic_size, types))
    return False


def is_arc4_static_size(wtype: wtypes.ARC4Type) -> bool:
    return not is_arc4_dynamic_size(wtype)


def determine_arc4_tuple_head_size(
    types: Sequence[wtypes.ARC4Type], *, round_end_result: bool
) -> int:
    bit_size = 0
    for t, next_t in zip_longest(types, types[1:]):
        size = 16 if is_arc4_dynamic_size(t) else get_arc4_fixed_bit_size(t)
        bit_size += size
        if t == wtypes.arc4_bool_wtype and next_t != t and (round_end_result or next_t):
            bit_size = round_bits_to_nearest_bytes(bit_size)
    return bit_size


_UINT_REGEX = re.compile(r"^uint(?P<n>[0-9]+)$")
_UFIXED_REGEX = re.compile(r"^ufixed(?P<n>[0-9]+)x(?P<m>[0-9]+)$")
_FIXED_ARRAY_REGEX = re.compile(r"^(?P<type>.+)\[(?P<size>[0-9]+)]$")
_DYNAMIC_ARRAY_REGEX = re.compile(r"^(?P<type>.+)\[]$")
_TUPLE_REGEX = re.compile(r"^\((?P<types>.+)\)$")
_ARC4_WTYPE_MAPPING = {
    "bool": wtypes.arc4_bool_wtype,
    "string": wtypes.arc4_string_wtype,
    "account": wtypes.account_wtype,
    "application": wtypes.application_wtype,
    "asset": wtypes.asset_wtype,
    "void": wtypes.void_wtype,
    **{
        t.name if t else "txn": wtypes.WGroupTransaction.from_type(t)
        for t in constants.TRANSACTION_TYPE_TO_CLS
    },
    "address": wtypes.arc4_address_type,
    "byte": wtypes.arc4_byte_type,
    "byte[]": wtypes.arc4_dynamic_bytes,
}


def make_dynamic_array_wtype(
    element_type: wtypes.WType, location: SourceLocation | None
) -> wtypes.ARC4DynamicArray:
    if not wtypes.is_arc4_encoded_type(element_type):
        raise CodeError(f"Invalid element type for arc4.DynamicArray: {element_type}", location)
    return wtypes.ARC4DynamicArray.from_element_type(element_type)


def make_static_array_wtype(
    element_type: wtypes.WType, size: int, location: SourceLocation | None
) -> wtypes.ARC4StaticArray:
    if not wtypes.is_arc4_encoded_type(element_type):
        raise CodeError(f"Invalid element type for arc4.StaticArray: {element_type}", location)
    return wtypes.ARC4StaticArray.from_element_type_and_size(element_type, int(size))


def make_tuple_wtype(
    types: Iterable[wtypes.WType], location: SourceLocation | None
) -> wtypes.ARC4Tuple:
    arc4_types = list[wtypes.ARC4Type]()
    for typ in types:
        if wtypes.is_arc4_encoded_type(typ):
            arc4_types.append(typ)
        else:
            raise CodeError(f"Invalid type for arc4.Tuple element: {typ}", location)
    return wtypes.ARC4Tuple.from_types(arc4_types)


def arc4_to_wtype(typ: str, location: SourceLocation | None = None) -> wtypes.WType:
    try:
        return _ARC4_WTYPE_MAPPING[typ]
    except KeyError:
        pass
    if uint := _UINT_REGEX.match(typ):
        n = uint.group("n")
        return wtypes.ARC4UIntN.from_scale(int(n))
    if ufixed := _UFIXED_REGEX.match(typ):
        n, m = ufixed.group("n", "m")
        return wtypes.ARC4UFixedNxM.from_scale_and_precision(int(n), int(m))
    if fixed_array := _FIXED_ARRAY_REGEX.match(typ):
        arr_type, size = fixed_array.group("type", "size")
        element_type = arc4_to_wtype(arr_type, location)
        return make_static_array_wtype(element_type, int(size), location)
    if dynamic_array := _DYNAMIC_ARRAY_REGEX.match(typ):
        arr_type = dynamic_array.group("type")
        element_type = arc4_to_wtype(arr_type, location)
        return make_dynamic_array_wtype(element_type, location)
    if tuple_match := _TUPLE_REGEX.match(typ):
        tuple_types = [
            arc4_to_wtype(x, location) for x in split_tuple_types(tuple_match.group("types"))
        ]
        return make_tuple_wtype(tuple_types, location)
    raise CodeError(f"Unknown ARC4 type '{typ}'", location)


def split_tuple_types(types: str) -> Iterable[str]:
    """Splits inner tuple types into individual elements.

    e.g. "uint64,(uint8,string),bool" becomes ["uint64", "(uint8,string)", "bool"]
    """
    tuple_level = 0
    last_idx = 0
    for idx, tok in enumerate(types):
        if tok == "(":
            tuple_level += 1
        elif tok == ")":
            tuple_level -= 1
        if tok == "," and tuple_level == 0:
            yield types[last_idx:idx]
            last_idx = idx + 1
    yield types[last_idx:]


def wtype_to_arc4(wtype: wtypes.WType, loc: SourceLocation | None = None) -> str:
    match wtype:
        case (
            wtypes.void_wtype
            | wtypes.asset_wtype
            | wtypes.account_wtype
            | wtypes.application_wtype
            | wtypes.uint64_wtype
            | wtypes.bool_wtype
            | wtypes.string_wtype
        ):
            return wtype.name
        case wtypes.biguint_wtype:
            return "uint512"
        case wtypes.bytes_wtype:
            return "byte[]"
        case wtypes.ARC4Type(alias=alias) if alias is not None:
            return alias
        case wtypes.ARC4UIntN() | wtypes.ARC4UFixedNxM():
            return wtype.name.removeprefix("arc4.")
        case wtypes.WGroupTransaction(transaction_type=transaction_type):
            return transaction_type.name if transaction_type else "txn"
        case wtypes.ARC4DynamicArray(element_type=inner_type):
            return f"{wtype_to_arc4(inner_type, loc)}[]"
        case wtypes.ARC4StaticArray(element_type=inner_type, array_size=size):
            return f"{wtype_to_arc4(inner_type, loc)}[{size}]"
        case (
            wtypes.ARC4Tuple(types=types)
            | wtypes.ARC4Struct(types=types)
            | wtypes.WTuple(types=types)
        ):
            item_types = ",".join([wtype_to_arc4(item) for item in types])
            return f"({item_types})"
    raise InternalError(f"Unhandled ARC4 type: {wtype}", loc)


def get_abi_signature(subroutine: awst_nodes.ContractMethod, config: ARC4MethodConfig) -> str:
    arg_types = [wtype_to_arc4(a.wtype, a.source_location) for a in subroutine.args]
    return_type = wtype_to_arc4(subroutine.return_type, subroutine.source_location)
    return f"{config.name}({','.join(arg_types)}){return_type}"
