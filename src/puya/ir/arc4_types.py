import typing

import attrs
from immutabledict import immutabledict

from puya.awst import wtypes
from puya.awst.visitors import ARC4WTypeVisitor, WTypeVisitor
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


class _ARC4EncodedWTypeConverterVisitor(WTypeVisitor[wtypes.ARC4Type | None]):
    @typing.override
    def visit_basic_type(self, wtype: wtypes.WType) -> wtypes.ARC4Type | None:
        match wtype:
            case wtypes.account_wtype:
                return wtypes.arc4_address_alias
            case wtypes.bool_wtype:
                return wtypes.arc4_bool_wtype
            case wtypes.uint64_wtype | wtypes.asset_wtype | wtypes.application_wtype:
                return wtypes.ARC4UIntN(n=64, source_location=None)
            case wtypes.biguint_wtype:
                return wtypes.ARC4UIntN(n=512, source_location=None)
            case wtypes.string_wtype:
                return wtypes.arc4_string_alias
            case _:
                return None

    @typing.override
    def visit_bytes_type(self, wtype: wtypes.BytesWType) -> wtypes.ARC4Type:
        if wtype.length is not None:
            return wtypes.ARC4StaticArray(
                element_type=wtypes.arc4_byte_alias,
                immutable=True,
                source_location=None,
                array_size=wtype.length,
            )
        return wtypes.ARC4DynamicArray(
            element_type=wtypes.arc4_byte_alias,
            immutable=True,
            source_location=None,
        )

    @typing.override
    def visit_enumeration_type(self, wtype: wtypes.WEnumeration) -> None:
        return None

    @typing.override
    def visit_group_transaction_type(self, wtype: wtypes.WGroupTransaction) -> None:
        return None

    @typing.override
    def visit_inner_transaction_type(self, wtype: wtypes.WInnerTransaction) -> None:
        return None

    @typing.override
    def visit_inner_transaction_fields_type(self, wtype: wtypes.WInnerTransactionFields) -> None:
        return None

    @typing.override
    def visit_reference_array(self, wtype: wtypes.ReferenceArray) -> None:
        return None

    @typing.override
    def visit_tuple_type(self, wtuple: wtypes.WTuple) -> wtypes.ARC4Type | None:
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

    @typing.override
    def visit_basic_arc4_type(self, wtype: wtypes.ARC4Type) -> wtypes.ARC4Type:
        return wtype

    @typing.override
    def visit_arc4_uint(self, wtype: wtypes.ARC4UIntN) -> wtypes.ARC4Type:
        return wtype

    @typing.override
    def visit_arc4_ufixed(self, wtype: wtypes.ARC4UFixedNxM) -> wtypes.ARC4Type:
        return wtype

    @typing.override
    def visit_arc4_tuple(self, wtype: wtypes.ARC4Tuple) -> wtypes.ARC4Type | None:
        converted_types = tuple(t.accept(self) for t in wtype.types)
        if None in converted_types:
            return None
        return attrs.evolve(wtype, types=converted_types)  # type: ignore[arg-type]

    @typing.override
    def visit_arc4_dynamic_array(self, wtype: wtypes.ARC4DynamicArray) -> wtypes.ARC4Type | None:
        element_type = wtype.element_type.accept(self)
        if element_type is None:
            return None
        return attrs.evolve(wtype, element_type=element_type)

    @typing.override
    def visit_arc4_static_array(self, wtype: wtypes.ARC4StaticArray) -> wtypes.ARC4Type | None:
        element_type = wtype.element_type.accept(self)
        if element_type is None:
            return None
        return attrs.evolve(wtype, element_type=element_type)

    @typing.override
    def visit_arc4_struct(self, wtype: wtypes.ARC4Struct) -> wtypes.ARC4Type | None:
        fields = {name: t.accept(self) for name, t in wtype.fields.items()}
        if None in fields.values():
            return None
        return attrs.evolve(wtype, fields=immutabledict(fields))


class _ARC4NameWTypeVisitor(ARC4WTypeVisitor[str]):
    def __init__(self, *, use_alias: bool = False):
        self._use_alias = use_alias
        self._arc4_converter = _ARC4EncodedWTypeConverterVisitor()

    def _wtype_arc4_name(self, wtype: wtypes.WType) -> str:
        arc4_wtype = wtype.accept(self._arc4_converter)
        if arc4_wtype is None:
            raise CodeError(f"unencodable ARC-4 type member on {wtype}")
        return arc4_wtype.accept(self)

    @typing.override
    def visit_basic_arc4_type(self, wtype: wtypes.ARC4Type) -> str:
        if self._use_alias and wtype.arc4_alias is not None:
            return wtype.arc4_alias
        match wtype:
            case wtypes.arc4_bool_wtype:
                return "bool"
            case _:
                raise InternalError(f"unexpected ARC-4 basic type: {wtype!r}")

    @typing.override
    def visit_arc4_uint(self, wtype: wtypes.ARC4UIntN) -> str:
        if self._use_alias and wtype.arc4_alias is not None:
            return wtype.arc4_alias
        return f"uint{wtype.n}"

    @typing.override
    def visit_arc4_ufixed(self, wtype: wtypes.ARC4UFixedNxM) -> str:
        if self._use_alias and wtype.arc4_alias is not None:
            return wtype.arc4_alias
        return f"ufixed{wtype.n}x{wtype.m}"

    @typing.override
    def visit_arc4_tuple(self, wtype: wtypes.ARC4Tuple) -> str:
        typing.assert_type(wtype.arc4_alias, None)
        item_arc4_names = [self._wtype_arc4_name(t) for t in wtype.types]
        return f"({','.join(item_arc4_names)})"

    @typing.override
    def visit_arc4_dynamic_array(self, wtype: wtypes.ARC4DynamicArray) -> str:
        if self._use_alias and wtype.arc4_alias is not None:
            return wtype.arc4_alias
        element_arc4_name = self._wtype_arc4_name(wtype.element_type)
        return f"{element_arc4_name}[]"

    @typing.override
    def visit_arc4_static_array(self, wtype: wtypes.ARC4StaticArray) -> str:
        if self._use_alias and wtype.arc4_alias is not None:
            return wtype.arc4_alias
        element_arc4_name = self._wtype_arc4_name(wtype.element_type)
        return f"{element_arc4_name}[{wtype.array_size}]"

    @typing.override
    def visit_arc4_struct(self, wtype: wtypes.ARC4Struct) -> str:
        typing.assert_type(wtype.arc4_alias, None)
        item_arc4_names = [self._wtype_arc4_name(t) for t in wtype.types]
        return f"({','.join(item_arc4_names)})"


def get_arc4_name(wtype: wtypes.ARC4Type, *, use_alias: bool = False) -> str:
    return wtype.accept(_ARC4NameWTypeVisitor(use_alias=use_alias))


def wtype_to_arc4(
    wtype: wtypes.WType,
    loc: SourceLocation,
    *,
    is_return: bool,
    use_reference_alias: bool = False,
) -> str:
    """
    Returns the ARC-4 name for a WType, non ARC-4 types are first converted to ARC-4 equivalents.
    Reference types and transaction types are only returned if allowed
    """
    match wtype:
        case (
            wtypes.asset_wtype
            | wtypes.account_wtype
            | wtypes.application_wtype
        ) if use_reference_alias:
            # if not use_reference_alias, these types are still allowed, but will
            # fall through to using the value encoding below
            return wtype.name
        case wtypes.WGroupTransaction(transaction_type=transaction_type):
            if is_return:
                raise CodeError("transactions are not supported as a return type", loc)
            return transaction_type.name if transaction_type else "txn"
        case wtypes.void_wtype:
            if not is_return:
                raise CodeError("void type is not supported at this location", loc)
            return wtype.name
    maybe_arc4_wtype = maybe_wtype_to_arc4_wtype(wtype)
    if maybe_arc4_wtype is None:
        raise CodeError("unsupported type for an ARC-4 method", loc)
    return get_arc4_name(maybe_arc4_wtype, use_alias=True)


def maybe_wtype_to_arc4_wtype(wtype: wtypes.WType) -> wtypes.ARC4Type | None:
    """
    Returns the ARC-4 equivalent type, note account, asset and application types are returned
    as their ARC-4 equivalent stack encoded values and not their ARC-4 reference alias types
    """
    return wtype.accept(_ARC4EncodedWTypeConverterVisitor())


def wtype_to_arc4_wtype(wtype: wtypes.WType, loc: SourceLocation | None) -> wtypes.ARC4Type:
    arc4_wtype = maybe_wtype_to_arc4_wtype(wtype)
    if arc4_wtype is None:
        raise CodeError(f"unsupported type for ARC-4 encoding {wtype}", loc)
    return arc4_wtype
