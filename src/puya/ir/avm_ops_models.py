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
class DynamicSignatures:
    immediate_index: int
    signatures: dict[str, OpSignature]


@attrs.define(kw_only=True)
class AVMOpData:
    op_code: str
    signature: OpSignature | DynamicSignatures
    immediate_types: Sequence[ImmediateKind] = attrs.field(default=())
    cost: int | None
    min_avm_version: int
