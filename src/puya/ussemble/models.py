import typing
from collections.abc import Mapping, Sequence

import attrs

from puya.parse import SourceLocation
from puya.ussemble.op_spec import OP_SPECS
from puya.ussemble.op_spec_models import OpSpec


class DebugEvent(typing.TypedDict, total=False):
    """Describes various attributes for a particular PC location"""

    subroutine: str
    """Subroutine name"""
    params: Mapping[str, str]
    """Describes a subroutines parameters and their types"""
    block: str
    """Name of a block"""
    stack_in: Sequence[str]
    """Variable names on the stack BEFORE the next op executes"""
    op: str
    """Op description"""
    callsub: str
    """The subroutine that is about to be called"""
    retsub: bool
    """Returns from current subroutine"""
    stack_out: Sequence[str]
    """Variable names on the stack AFTER the next op executes"""
    defined_out: Sequence[str]
    """Variable names that are defined AFTER the next op executes"""


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
    debug_info: bytes
