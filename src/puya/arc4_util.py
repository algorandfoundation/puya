from collections.abc import Iterable, Sequence
from itertools import zip_longest

from puya.awst import wtypes
from puya.awst.wtypes import ARC4Type
from puya.errors import CodeError, InternalError
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
        case wtypes.ARC4DynamicArray():
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


def make_tuple_wtype(
    types: Iterable[wtypes.WType], location: SourceLocation | None
) -> wtypes.ARC4Tuple:
    arc4_types = list[wtypes.ARC4Type]()
    for typ in types:
        if isinstance(typ, ARC4Type):
            arc4_types.append(typ)
        else:
            raise CodeError(f"Invalid type for arc4.Tuple element: {typ}", location)
    return wtypes.ARC4Tuple(arc4_types, location)


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
        case wtypes.ARC4Type(arc4_name=arc4_name):
            return arc4_name
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
        case wtypes.WGroupTransaction(transaction_type=transaction_type):
            return transaction_type.name if transaction_type else "txn"
        case wtypes.WTuple(types=types):
            item_types = ",".join([wtype_to_arc4(item) for item in types])
            return f"({item_types})"
        case _:
            raise CodeError(f"not an ARC4 type or native equivalent: {wtype}", loc)
