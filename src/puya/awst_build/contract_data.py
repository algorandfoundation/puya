import enum

import attrs

from puya.awst import wtypes
from puya.awst.nodes import BytesConstant, BytesEncoding, ContractReference, StateTotals
from puya.errors import InternalError
from puya.parse import SourceLocation
from puya.utils import StableSet


@enum.unique
class AppStorageDeclType(enum.Enum):
    local_proxy = enum.auto()
    global_proxy = enum.auto()
    global_direct = enum.auto()
    box = enum.auto()
    box_ref = enum.auto()
    box_map = enum.auto()


@attrs.frozen
class AppStorageDeclaration:
    member_name: str
    decl_type: AppStorageDeclType
    storage_wtype: wtypes.WType
    key_wtype: wtypes.WType | None = attrs.field()
    """Should only be set if the storage is a map"""
    key_override: BytesConstant | None
    """If a map type, then this is the prefix override"""
    source_location: SourceLocation
    defined_in: ContractReference
    description: str | None

    @key_wtype.validator
    def _key_wtype_validator(self, _attribute: object, key_wtype: wtypes.WType | None) -> None:
        has_key_type = key_wtype is not None
        is_map_type = self.decl_type is AppStorageDeclType.box_map
        if has_key_type != is_map_type:
            raise InternalError("key_wtype should only be set for box_map")

    @property
    def key(self) -> BytesConstant:
        if self.key_override is not None:
            return self.key_override
        return BytesConstant(
            value=self.member_name.encode("utf8"),
            encoding=BytesEncoding.utf8,
            source_location=self.source_location,
        )


@attrs.define
class ContractClassOptions:
    name_override: str | None
    scratch_slot_reservations: StableSet[int]
    state_totals: StateTotals | None
