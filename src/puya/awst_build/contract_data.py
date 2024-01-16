import enum

import attrs

from puya.awst.nodes import AppStateDefinition


@enum.unique
class AppStateDeclType(enum.Enum):
    local_proxy = enum.auto()
    global_proxy = enum.auto()
    global_direct = enum.auto()


@attrs.frozen
class AppStateDeclaration:
    state_def: AppStateDefinition
    decl_type: AppStateDeclType
