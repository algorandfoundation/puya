import re
import typing
from collections.abc import Callable, Iterable

import attrs
import mypy.nodes
import mypy.visitor

from puya import log
from puya.avm import TransactionType
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes

__all__ = [
    "arc4_to_pytype",
    "pytype_to_arc4",
    "pytype_to_arc4_pytype",
]

logger = log.get_logger(__name__)


def _is_arc4_struct(typ: pytypes.PyType) -> typing.TypeGuard[pytypes.StructType]:
    if not (pytypes.ARC4StructBaseType < typ):
        return False
    if not isinstance(typ, pytypes.StructType):
        raise InternalError(
            f"Type inherits from {pytypes.ARC4StructBaseType!r}"
            f" but structure type is {type(typ).__name__!r}"
        )
    return True


@attrs.frozen
class _DecoratorData:
    fullname: str
    args: list[tuple[str | None, mypy.nodes.Expression]]
    source_location: SourceLocation


def pytype_to_arc4_pytype(
    pytype: pytypes.PyType,
    on_error: Callable[[pytypes.PyType], pytypes.PyType],
) -> pytypes.PyType:
    match pytype:
        case pytypes.BoolType:
            return pytypes.ARC4BoolType
        case pytypes.NamedTupleType():
            return pytypes.StructType(
                base=pytypes.ARC4StructBaseType,
                desc=pytype.desc,
                name=pytype.name,
                fields={
                    name: pytype_to_arc4_pytype(t, on_error) for name, t in pytype.fields.items()
                },
                frozen=True,
                source_location=pytype.source_location,
            )
        case pytypes.ArrayType(generic=pytypes.GenericImmutableArrayType, items=items):
            result = pytypes.GenericARC4DynamicArrayType.parameterise(
                [pytype_to_arc4_pytype(items, on_error)], pytype.source_location
            )
            result2 = attrs.evolve(result, wtype=attrs.evolve(result.wtype, immutable=True))
            return result2
        case pytypes.TupleType():
            return pytypes.GenericARC4TupleType.parameterise(
                [pytype_to_arc4_pytype(t, on_error) for t in pytype.items], pytype.source_location
            )
        case pytypes.NoneType | pytypes.GroupTransactionType():
            return pytype

    if pytypes.UInt64Type <= pytype:
        return pytypes.ARC4UIntN_Aliases[64]
    elif pytypes.BigUIntType <= pytype:
        return pytypes.ARC4UIntN_Aliases[512]
    elif pytypes.BytesType <= pytype:
        return pytypes.ARC4DynamicBytesType
    elif pytypes.StringType <= pytype:
        return pytypes.ARC4StringType
    elif pytype.is_type_or_subtype(
        pytypes.ApplicationType, pytypes.AssetType, pytypes.AccountType
    ) or isinstance(pytype.wtype, wtypes.ARC4Type):
        return pytype
    else:
        return on_error(pytype)


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


def pytype_to_arc4(typ: pytypes.PyType, loc: SourceLocation | None = None) -> str:
    def on_error(bad_type: pytypes.PyType) -> typing.Never:
        raise CodeError(
            f"not an ARC-4 type or native equivalent: {bad_type}",
            loc or getattr(bad_type, "source_location", None),
        )

    arc4_pytype = pytype_to_arc4_pytype(typ, on_error)
    match arc4_pytype:
        case pytypes.NoneType:
            return "void"
        case pytypes.AssetType:
            return "asset"
        case pytypes.AccountType:
            return "account"
        case pytypes.ApplicationType:
            return "application"
        case pytypes.TransactionRelatedType(transaction_type=transaction_type):
            return transaction_type.name if transaction_type else "txn"
    wtype = arc4_pytype.wtype
    if not isinstance(wtype, wtypes.ARC4Type):
        raise CodeError(f"not an ARC-4 type or native equivalent: {wtype}", loc)
    return wtype.arc4_name


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
