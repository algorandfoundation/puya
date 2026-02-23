import re
from collections.abc import Iterable

from puya import log
from puya.avm import TransactionType
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes

__all__ = [
    "arc4_to_pytype",
    "split_tuple_types",
]

logger = log.get_logger(__name__)

_UINT_REGEX = re.compile(r"^uint(?P<n>[0-9]+)$")
_UFIXED_REGEX = re.compile(r"^ufixed(?P<n>[0-9]+)x(?P<m>[0-9]+)$")
_FIXED_ARRAY_REGEX = re.compile(r"^(?P<type>.+)\[(?P<size>[0-9]+)]$")
_DYNAMIC_ARRAY_REGEX = re.compile(r"^(?P<type>.+)\[]$")
_TUPLE_REGEX = re.compile(r"^\((?P<types>.+)\)$")
_ARC4_PYTYPE_MAPPING = {
    "bool": pytypes.ARC4BoolType,
    "string": pytypes.ARC4StringType,
    "account": pytypes.AccountType,
    "application": pytypes.ApplicationType,
    "asset": pytypes.AssetType,
    "void": pytypes.NoneType,
    "txn": pytypes.GroupTransactionTypes[None],
    **{t.name: pytypes.GroupTransactionTypes[t] for t in TransactionType},
    "address": pytypes.ARC4AddressType,
    "byte": pytypes.ARC4ByteType,
    "byte[]": pytypes.ARC4DynamicBytesType,
}
_PYTYPE_ARC4_MAPPING = {v: k for k, v in _ARC4_PYTYPE_MAPPING.items()}
assert len(_ARC4_PYTYPE_MAPPING) == len(_PYTYPE_ARC4_MAPPING)


def arc4_to_pytype(typ: str, location: SourceLocation | None = None) -> pytypes.PyType:
    if known_typ := _ARC4_PYTYPE_MAPPING.get(typ):
        return known_typ
    if uint := _UINT_REGEX.match(typ):
        n = int(uint.group("n"))
        n_typ = pytypes.TypingLiteralType(value=n, source_location=None)
        if n <= 64:
            return pytypes.GenericARC4UIntNType.parameterise([n_typ], location)
        else:
            return pytypes.GenericARC4BigUIntNType.parameterise([n_typ], location)
    if ufixed := _UFIXED_REGEX.match(typ):
        n, m = map(int, ufixed.group("n", "m"))
        n_typ = pytypes.TypingLiteralType(value=n, source_location=None)
        m_typ = pytypes.TypingLiteralType(value=m, source_location=None)
        if n <= 64:
            return pytypes.GenericARC4UFixedNxMType.parameterise([n_typ, m_typ], location)
        else:
            return pytypes.GenericARC4BigUFixedNxMType.parameterise([n_typ, m_typ], location)
    if fixed_array := _FIXED_ARRAY_REGEX.match(typ):
        arr_type, size_str = fixed_array.group("type", "size")
        size = int(size_str)
        size_typ = pytypes.TypingLiteralType(value=size, source_location=None)
        element_type = arc4_to_pytype(arr_type, location)
        return pytypes.GenericARC4StaticArrayType.parameterise([element_type, size_typ], location)
    if dynamic_array := _DYNAMIC_ARRAY_REGEX.match(typ):
        arr_type = dynamic_array.group("type")
        element_type = arc4_to_pytype(arr_type, location)
        return pytypes.GenericARC4DynamicArrayType.parameterise([element_type], location)
    if tuple_match := _TUPLE_REGEX.match(typ):
        tuple_types = [
            arc4_to_pytype(x, location) for x in split_tuple_types(tuple_match.group("types"))
        ]
        return pytypes.GenericARC4TupleType.parameterise(tuple_types, location)
    raise CodeError(f"unknown ARC-4 type '{typ}'", location)


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
