import enum
from collections.abc import Sequence

import attrs

from puya.ir.types_ import IRType


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
    args: Sequence[IRType]
    returns: Sequence[IRType]


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
