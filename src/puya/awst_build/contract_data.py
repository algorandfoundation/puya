import enum

import attrs

from puya.awst.nodes import AppStorageKind, BytesConstant, ContractReference, StateTotals
from puya.awst.wtypes import WType
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
    kind: AppStorageKind
    storage_wtype: WType
    key_wtype: WType | None
    key_override: BytesConstant | None
    decl_type: AppStorageDeclType
    source_location: SourceLocation
    defined_in: ContractReference
    description: str | None


@attrs.define
class ContractClassOptions:
    name_override: str | None
    scratch_slot_reservations: StableSet[int]
    state_totals: StateTotals | None
