import typing
from collections.abc import Mapping, Sequence

import attrs

from puya.parse import SourceLocation
from puya.ussemble.op_spec import OP_SPECS
from puya.ussemble.op_spec_models import OpSpec


class DebugEvent(typing.TypedDict, total=False):
    subroutine: str
    block: str
    op: str
    callsub: str
    retsub: bool
    params: Mapping[str, str]
    """Also defines the p-stack, which holds the parameters passed via the stack to a function"""
    stack_in: Sequence[str]
    stack_out: Sequence[str]
    """The variables defined relative to a function's current subroutine frame"""
    defined_out: Sequence[str]


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

    def __str__(self) -> str:
        return f"{self.op_code} {' '.join(map(_immediate_desc, self.immediates))}".rstrip()


def _immediate_desc(
    imm: int | bytes | Label | Sequence[int] | Sequence[bytes] | Sequence[Label] | str,
) -> str:
    if isinstance(imm, str):
        return imm
    if isinstance(imm, Label):
        return imm.name
    elif isinstance(imm, bytes):
        return f"0x{imm.hex()}"
    elif isinstance(imm, Sequence):
        return " ".join(map(_immediate_desc, imm))
    else:
        return str(imm)


Node = Label | AVMOp


@attrs.frozen
class AssembledProgram:
    bytecode: bytes
    debug_info: bytes
