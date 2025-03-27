import typing

from puya.awst import wtypes
from puya.errors import CodeError
from puya.parse import SourceLocation


def wtype_to_arc4(wtype: wtypes.WType, loc: SourceLocation | None = None) -> str:
    """Returns the ARC-4 name for a WType, reference types and transaction types are return their
    applicable ARC-4 aliases, other non ARC-4 types return their ARC-4 equivalents"""
    match wtype:
        case wtypes.ARC4Type(arc4_name=arc4_name):
            return arc4_name
        case (
            wtypes.void_wtype
            | wtypes.asset_wtype
            | wtypes.account_wtype
            | wtypes.application_wtype
        ):
            return wtype.name
        case wtypes.WGroupTransaction(transaction_type=transaction_type):
            return transaction_type.name if transaction_type else "txn"
    converted = wtype_to_arc4_wtype(wtype, loc)
    return wtype_to_arc4(converted, loc)


def maybe_wtype_to_arc4_wtype(wtype: wtypes.WType) -> wtypes.ARC4Type | None:
    """Returns the ARC-4 equivalent type, note account, asset and application types are returned
    as their ARC-4 equivalent stack encoded values and not their ARC-4 reference alias types"""
    match wtype:
        case wtypes.ARC4Type() as arc4_wtype:
            return arc4_wtype
        case wtypes.account_wtype:
            return wtypes.arc4_address_alias
        case wtypes.bool_wtype:
            return wtypes.arc4_bool_wtype
        case wtypes.uint64_wtype | wtypes.asset_wtype | wtypes.application_wtype:
            return wtypes.ARC4UIntN(n=64, source_location=None)
        case wtypes.biguint_wtype:
            return wtypes.ARC4UIntN(n=512, source_location=None)
        case wtypes.bytes_wtype:
            return wtypes.ARC4DynamicArray(
                element_type=wtypes.arc4_byte_alias,
                immutable=True,
                source_location=None,
            )
        case wtypes.string_wtype:
            return wtypes.arc4_string_alias
        case wtypes.StackArray(element_type=element_type):
            arc4_element_type = maybe_wtype_to_arc4_wtype(element_type)
            if arc4_element_type is None:
                return None
            return wtypes.ARC4DynamicArray(element_type=arc4_element_type, immutable=True)
        case wtypes.WTuple() as wtuple:
            arc4_item_types = []
            for t in wtuple.types:
                arc4_type = maybe_wtype_to_arc4_wtype(t)
                if arc4_type is None:
                    return None
                arc4_item_types.append(arc4_type)
            if wtuple.fields:
                arc4_fields = dict(zip(wtuple.fields, arc4_item_types, strict=True))
                return wtypes.ARC4Struct(
                    name=wtuple.name, desc=wtuple.desc, frozen=True, fields=arc4_fields
                )
            else:
                return wtypes.ARC4Tuple(types=arc4_item_types, source_location=None)
        case _:
            return None


def wtype_to_arc4_wtype(wtype: wtypes.WType, loc: SourceLocation | None) -> wtypes.ARC4Type:
    arc4_wtype = maybe_wtype_to_arc4_wtype(wtype)
    if arc4_wtype is None:
        raise CodeError(f"unsupported type for ARC-4 encoding {wtype}", loc)
    return arc4_wtype


# note that this function is typed only as StackArray -> ARC4DynamicArray, because that is
# the only currently supported combo, so it's easier to type it as that rather than check/assert
# etc in the callers.
# but that should change, in theory it should be able to take NativeArray -> ARC4Array (or other??)
def effective_array_encoding(
    array_type: wtypes.StackArray, loc: SourceLocation | None
) -> wtypes.ARC4DynamicArray:
    """If a native stack array is effectively ARC-4-encoded, return that equivalent type here."""
    arc4_element_type = maybe_wtype_to_arc4_wtype(array_type.element_type)
    if arc4_element_type is None:
        # we flat out don't support this (yet?), so always raise a CodeError
        # this is an internal detail to the current IR implementation of this type,
        # so this is the right spot to do this validation in currently
        raise CodeError("unsupported array element type", loc)
    return wtypes.ARC4DynamicArray(element_type=arc4_element_type, immutable=True)


def is_equivalent_effective_array_encoding(
    array_type: wtypes.StackArray, encoding_type: wtypes.WType, loc: SourceLocation | None
) -> bool:
    effective_type = effective_array_encoding(array_type, loc)
    typing.assert_type(effective_type, wtypes.ARC4DynamicArray)  # could be expanded to ARC4Type
    return (
        isinstance(encoding_type, wtypes.ARC4Type)
        and effective_type.arc4_name == encoding_type.arc4_name
    )
