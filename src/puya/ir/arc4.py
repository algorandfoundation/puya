from collections.abc import Sequence
from itertools import zip_longest

from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir.arc4_types import wtype_to_arc4_wtype
from puya.parse import SourceLocation
from puya.utils import round_bits_to_nearest_bytes


def is_arc4_dynamic_size(wtype: wtypes.ARC4Type) -> bool:
    match wtype:
        case wtypes.ARC4DynamicArray():
            return True
        case wtypes.ARC4StaticArray(element_type=element_type):
            return is_arc4_dynamic_size(wtype_to_arc4_wtype(element_type, None))
        case wtypes.ARC4Tuple(types=types) | wtypes.ARC4Struct(types=types):
            return any(is_arc4_dynamic_size(wtype_to_arc4_wtype(t, None)) for t in types)
    return False


def is_arc4_static_size(wtype: wtypes.ARC4Type) -> bool:
    return not is_arc4_dynamic_size(wtype)


def get_arc4_static_bit_size(wtype: wtypes.ARC4Type) -> int:
    if is_arc4_dynamic_size(wtype):
        raise InternalError(f"Cannot get fixed bit size for a dynamic ABI type: {wtype}")
    match wtype:
        case wtypes.arc4_bool_wtype:
            return 1
        case wtypes.ARC4UIntN(n=n) | wtypes.ARC4UFixedNxM(n=n):
            return n
        case wtypes.ARC4StaticArray(element_type=element_type, array_size=array_size):
            element_type = wtype_to_arc4_wtype(element_type, None)
            el_size = get_arc4_static_bit_size(element_type)
            return round_bits_to_nearest_bytes(array_size * el_size)
        case wtypes.ARC4Tuple(types=types) | wtypes.ARC4Struct(types=types):
            arc4_types = [wtype_to_arc4_wtype(t, None) for t in types]
            return get_arc4_tuple_head_size(arc4_types, round_end_result=True)
    raise InternalError(f"Unexpected ABI wtype: {wtype}")


def get_arc4_tuple_head_size(types: Sequence[wtypes.WType], *, round_end_result: bool) -> int:
    bit_size = 0
    arc4_types = [wtype_to_arc4_wtype(t, SourceLocation(file=None, line=1)) for t in types]
    for t, next_t in zip_longest(arc4_types, arc4_types[1:]):
        size = 16 if is_arc4_dynamic_size(t) else get_arc4_static_bit_size(t)
        bit_size += size
        if t == wtypes.arc4_bool_wtype and next_t != t and (round_end_result or next_t):
            bit_size = round_bits_to_nearest_bytes(bit_size)
    return bit_size
