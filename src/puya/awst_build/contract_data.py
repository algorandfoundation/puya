from functools import cached_property

import attrs

from puya.awst.nodes import (
    AppStorageDefinition,
    AppStorageKind,
    BytesConstant,
    BytesEncoding,
    ContractReference,
    StateTotals,
)
from puya.awst_build import pytypes
from puya.parse import SourceLocation
from puya.utils import StableSet


@attrs.frozen
class AppStorageDeclaration:
    member_name: str
    typ: pytypes.PyType
    key_override: BytesConstant | None
    """If a map type, then this is the prefix override"""
    source_location: SourceLocation
    defined_in: ContractReference
    description: str | None

    @property
    def key(self) -> BytesConstant:
        if self.key_override is not None:
            return self.key_override
        return BytesConstant(
            value=self.member_name.encode("utf8"),
            encoding=BytesEncoding.utf8,
            source_location=self.source_location,
        )

    @cached_property
    def definition(self) -> AppStorageDefinition:
        key_wtype = None
        match self.typ:
            case pytypes.StorageProxyType(generic=pytypes.GenericLocalStateType, content=content):
                kind = AppStorageKind.account_local
            case pytypes.StorageProxyType(generic=pytypes.GenericGlobalStateType, content=content):
                kind = AppStorageKind.app_global
            case pytypes.BoxRefType:
                kind = AppStorageKind.box
                content = pytypes.BytesType
            case pytypes.StorageProxyType(generic=pytypes.GenericBoxType, content=content):
                kind = AppStorageKind.box
            case pytypes.StorageMapProxyType(
                generic=pytypes.GenericBoxMapType, content=content, key=key_typ
            ):
                kind = AppStorageKind.box
                key_wtype = key_typ.wtype
            case _ as content:
                kind = AppStorageKind.app_global
        return AppStorageDefinition(
            key=self.key,
            description=self.description,
            storage_wtype=content.wtype,
            key_wtype=key_wtype,
            source_location=self.source_location,
            kind=kind,
            member_name=self.member_name,
        )


@attrs.define
class ContractClassOptions:
    name_override: str | None
    scratch_slot_reservations: StableSet[int]
    state_totals: StateTotals | None
