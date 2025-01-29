import typing
from collections.abc import Callable

from algopy import UInt64, urange

@typing.final
class LogicSig:
    """A logic signature"""

@typing.overload
def logicsig(sub: Callable[[], bool | UInt64], /) -> LogicSig: ...
@typing.overload
def logicsig(
    *,
    name: str = ...,
    avm_version: int = ...,
    scratch_slots: urange | tuple[int | urange, ...] | list[int | urange] = (),
) -> Callable[[Callable[[], bool | UInt64]], LogicSig]:
    """Decorator to indicate a function is a logic signature"""
