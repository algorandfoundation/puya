import typing
from collections.abc import Sequence
from itertools import zip_longest

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import InternalError
from puya.metadata import ARC4MethodConfig
from puya.parse import SourceLocation
from puya.utils import round_bits_to_nearest_bytes


def get_arc4_fixed_bit_size(wtype: wtypes.WType) -> int | None:
    match wtype:
        case wtypes.arc4_bool_wtype:
            return 1
        case wtypes.ARC4UIntN(n=n) | wtypes.ARC4UFixedNxM(n=n):
            return n
        case wtypes.arc4_string_wtype | wtypes.ARC4DynamicArray():
            return None
        case wtypes.ARC4StaticArray(element_type=element_type, array_size=array_size):
            el_size = get_arc4_fixed_bit_size(element_type)
            return el_size and round_bits_to_nearest_bytes(array_size * el_size)
        case wtypes.ARC4Tuple(types=types) | wtypes.ARC4Struct(types=types):
            return _get_size_of_sequence(types, dynamic_size=None)
    raise InternalError(f"Unexpected ABI wtype: {wtype}")


def is_arc4_dynamic_size(wtype: wtypes.WType) -> bool:
    return get_arc4_fixed_bit_size(wtype) is None


def determine_arc4_tuple_head_size(
    types: Sequence[wtypes.WType], *, round_end_result: bool
) -> int:
    return _get_size_of_sequence(
        types,
        dynamic_size=16,  # size of "pointer"
        round_end_result=round_end_result,
    )


def wtype_to_arc4(wtype: wtypes.WType, loc: SourceLocation | None = None) -> str:
    match wtype:
        case (
            wtypes.void_wtype
            | wtypes.asset_wtype
            | wtypes.account_wtype
            | wtypes.application_wtype
        ):
            return wtype.name
        case wtypes.ARC4Type(alias=alias) if alias is not None:
            return alias
        case wtypes.ARC4UIntN() | wtypes.ARC4UFixedNxM():
            return wtype.name.removeprefix("arc4.")
        case wtypes.WTransaction(transaction_type=transaction_type):
            if transaction_type is None:
                raise InternalError(
                    "Only specific transaction types should appear as ARC4 types", loc
                )
            else:
                return transaction_type.name
        case wtypes.ARC4DynamicArray(element_type=inner_type):
            return f"{wtype_to_arc4(inner_type, loc)}[]"
        case wtypes.ARC4StaticArray(element_type=inner_type, array_size=size):
            return f"{wtype_to_arc4(inner_type, loc)}[{size}]"
        case wtypes.ARC4Tuple(types=types) | wtypes.ARC4Struct(types=types):
            item_types = ",".join([wtype_to_arc4(item) for item in types])
            return f"({item_types})"
    raise InternalError(f"Unhandled ARC4 type: {wtype}", loc)


def get_abi_signature(subroutine: awst_nodes.ContractMethod, config: ARC4MethodConfig) -> str:
    arg_types = [wtype_to_arc4(a.wtype, a.source_location) for a in subroutine.args]
    return_type = wtype_to_arc4(subroutine.return_type, subroutine.source_location)
    return f"{config.name}({','.join(arg_types)}){return_type}"


_TIntOrNone = typing.TypeVar("_TIntOrNone", int, None)


def _get_size_of_sequence(
    types: Sequence[wtypes.WType], *, dynamic_size: _TIntOrNone, round_end_result: bool = True
) -> int | _TIntOrNone:
    bit_size = 0
    for t, next_t in zip_longest(types, types[1:]):
        size = get_arc4_fixed_bit_size(t) or dynamic_size
        if size is None:
            return None
        bit_size += size
        if t == wtypes.arc4_bool_wtype and next_t != t and (round_end_result or next_t):
            bit_size = round_bits_to_nearest_bytes(bit_size)
    return bit_size
