import typing
from collections.abc import Callable

from algopy import UInt64, urange

_P = typing.ParamSpec("_P")

@typing.final
class LogicSig:
    """A logic signature"""

@typing.overload
def logicsig(sub: Callable[_P, bool | UInt64], /) -> LogicSig: ...
@typing.overload
def logicsig(
    *,
    name: str = ...,
    avm_version: int = ...,
    autosalt: bool = ...,
    scratch_slots: urange | tuple[int | urange, ...] | list[int | urange] = (),
    validate_encoding: typing.Literal["unsafe_disabled", "args"] = ...,
) -> Callable[[Callable[_P, bool | UInt64]], LogicSig]:
    """Decorator to indicate a function is a logic signature

    :param name:
     The name used for the logic signature in compiler outputs (e.g. the output TEAL file name).
     Defaults to the decorated function's name.

    :param avm_version:
     Determines which AVM version to use, this affects what operations are supported.
     Defaults to value provided supplied on command line (which defaults to current mainnet version)

    :param autosalt:
     Controls whether the assembler adds an off-curve salt so the logicsig address cannot decode
     to a valid public key.
     Logicsigs are salted by default on any AVM version. Set `False` to disable it. A matching
     `#pragma autosalt` is emitted to the TEAL output.

    :param scratch_slots:
     Allows you to mark a slot ID or range of slot IDs as "off limits" to Puya.
     These slot ID(s) will never be written to or otherwise manipulated by the compiler itself.
     This is particularly useful in combination with `algopy.op.gload_bytes` / `algopy.op.gload_uint64`
     which lets a contract in a group transaction read from the scratch slots of a logic signature
     that occurs earlier in the transaction group.

    :param validate_encoding:
     Whether to validate that the logic signature's arguments are correctly ABI-encoded when they
     are read (via the `arg` opcode). `"args"` inserts validation; `"unsafe_disabled"` skips it to
     save opcodes when the arguments are trusted. Defaults to the value supplied on the command line.
    """
