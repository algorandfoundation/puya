import enum
import typing

import attrs

from puya.awst.nodes import AppStateKind, StateTotals
from puya.awst.wtypes import WType
from puya.parse import SourceLocation
from puya.utils import StableSet


@enum.unique
class AppStateDeclType(enum.Enum):
    local_proxy = enum.auto()
    global_proxy = enum.auto()
    global_direct = enum.auto()


@attrs.frozen
class AppStateDeclaration:
    member_name: str
    kind: AppStateKind
    storage_wtype: WType
    decl_type: AppStateDeclType
    source_location: SourceLocation


@attrs.define
class ContractClassOptions:
    name_override: str | None
    scratch_slot_reservations: StableSet[int]
    state_totals: StateTotals | None


@attrs.frozen
class BoxDeclaration:
    member_name: str
    wtype: WType
    source_location: SourceLocation


AppStorageDeclaration: typing.TypeAlias = AppStateDeclaration | BoxDeclaration
