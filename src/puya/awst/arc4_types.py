from immutabledict import immutabledict

from puya.awst import wtypes
from puya.errors import CodeError
from puya.parse import SourceLocation


def wtype_to_arc4(wtype: wtypes.WType, loc: SourceLocation | None = None) -> str:
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
    converted = maybe_avm_to_arc4_equivalent_type(wtype)
    if converted is None:
        raise CodeError(f"not an ARC4 type or native equivalent: {wtype}", loc)
    return wtype_to_arc4(converted, loc)


def maybe_avm_to_arc4_equivalent_type(wtype: wtypes.WType) -> wtypes.ARC4Type | None:
    match wtype:
        case wtypes.bool_wtype:
            return wtypes.arc4_bool_wtype
        case wtypes.uint64_wtype:
            return wtypes.ARC4UIntN(n=64, source_location=None)
        case wtypes.biguint_wtype:
            return wtypes.ARC4UIntN(n=512, source_location=None)
        case wtypes.bytes_wtype:
            return wtypes.ARC4DynamicArray(
                element_type=wtypes.arc4_byte_alias, native_type=wtype, source_location=None
            )
        case wtypes.string_wtype:
            return wtypes.arc4_string_alias
        case wtypes.WTuple(types=tuple_item_types) as wtuple:
            arc4_item_types = []
            for t in tuple_item_types:
                if isinstance(t, wtypes.ARC4Type):
                    arc4_item_types.append(t)
                else:
                    converted = maybe_avm_to_arc4_equivalent_type(t)
                    if converted is None:
                        return None
                    arc4_item_types.append(converted)
            if wtuple.fields:
                return wtypes.ARC4Struct(
                    name=wtuple.name,
                    desc=wtuple.desc,
                    frozen=True,
                    fields=immutabledict(zip(wtuple.fields, arc4_item_types, strict=True)),
                )
            else:
                return wtypes.ARC4Tuple(types=arc4_item_types, source_location=None)
        case _:
            return None
