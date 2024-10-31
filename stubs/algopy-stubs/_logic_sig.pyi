import typing
from collections.abc import Callable

from algopy import UInt64

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
) -> Callable[[Callable[[], bool | UInt64]], LogicSig]:
    """Decorator to indicate a function is a logic signature"""
