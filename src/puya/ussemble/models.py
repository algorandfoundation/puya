from collections.abc import Mapping, Sequence

import attrs

from puya.compilation_artifacts import DebugInfo
from puya.parse import SourceLocation
from puya.ussemble.op_spec import OP_SPECS
from puya.ussemble.op_spec_models import OpSpec


@attrs.frozen(str=False)
class Label:
    name: str

    def __str__(self) -> str:
        return f"{self.name}:"


@attrs.frozen(str=False, eq=False)
class AVMOp:
    source_location: SourceLocation | None
    op_code: str
    immediates: Sequence[
        Sequence[int] | int | Sequence[bytes] | bytes | Sequence[Label] | Label | str
    ]

    @property
    def op_spec(self) -> OpSpec:
        return OP_SPECS[self.op_code]


@attrs.frozen
class AssembledProgram:
    bytecode: bytes
    debug_info: DebugInfo
    template_variables: Mapping[str, int | bytes | None]
    """Indicates template variable values used in compilation"""
    stats: Mapping[str, int]
