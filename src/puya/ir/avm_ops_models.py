import enum
from collections.abc import Sequence

import attrs


class StackType(enum.StrEnum):
    uint64 = enum.auto()
    bytes = "[]byte"
    bool = enum.auto()
    address = enum.auto()
    address_or_index = enum.auto()
    any = enum.auto()
    bigint = enum.auto()
    box_name = "boxName"
    asset = enum.auto()
    application = enum.auto()
    state_key = "stateKey"

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


class RunMode(enum.StrEnum):
    app = enum.auto()
    lsig = enum.auto()
    any = enum.auto()

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


class ImmediateKind(enum.StrEnum):
    uint8 = enum.auto()
    arg_enum = enum.auto()

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


@attrs.frozen
class OpSignature:
    args: Sequence[StackType]
    returns: Sequence[StackType]


@attrs.frozen
class Variant:
    signature: OpSignature
    enum: str | None
    supported_modes: RunMode
    min_avm_version: int


@attrs.frozen
class DynamicVariants:
    immediate_index: int
    variant_map: dict[str, Variant]


@attrs.define(kw_only=True)
class AVMOpData:
    op_code: str
    variants: Variant | DynamicVariants
    immediate_types: Sequence[ImmediateKind] = attrs.field(default=())
    cost: int | None
    min_avm_version: int
    supported_modes: RunMode
