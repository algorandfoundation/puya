import enum
from collections.abc import Mapping

import attrs


class ImmediateKind(enum.StrEnum):
    uint8 = enum.auto()
    int8 = enum.auto()
    label = enum.auto()
    varuint = enum.auto()
    bytes = enum.auto()

    # array types
    label_array = enum.auto()
    varuint_array = enum.auto()
    bytes_array = enum.auto()

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


@attrs.frozen
class ImmediateEnum:
    codes: Mapping[str, int]


@attrs.frozen
class OpSpec:
    name: str
    code: int
    immediates: list[ImmediateKind | ImmediateEnum]
