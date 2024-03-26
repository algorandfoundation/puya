import typing
from collections.abc import Callable

from algopy import UInt64

class LogicSig:
    """A logic signature"""

@typing.overload
def logicsig(sub: Callable[[], bool | UInt64], /) -> LogicSig: ...
@typing.overload
def logicsig(*, name: str) -> Callable[[Callable[[], bool | UInt64]], LogicSig]:
    """Decorator to indicate a function is a logic signature"""
