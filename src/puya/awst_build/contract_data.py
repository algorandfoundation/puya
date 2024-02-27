import enum

import attrs

from puya.awst.nodes import AppStateDefinition
from puya.utils import StableSet


@enum.unique
class AppStateDeclType(enum.Enum):
    local_proxy = enum.auto()
    global_proxy = enum.auto()
    global_direct = enum.auto()


@attrs.frozen
class AppStateDeclaration:
    state_def: AppStateDefinition
    decl_type: AppStateDeclType


@attrs.define
class ContractClassOptions:
    name_override: str | None
    scratch_slot_reservations: StableSet[int]
