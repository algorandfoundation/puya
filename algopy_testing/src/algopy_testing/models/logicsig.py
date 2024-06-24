from __future__ import annotations

import typing
from functools import wraps

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    import algopy


class LogicSig:
    """A logic signature"""

    def __init__(self, func: Callable[[], bool | algopy.UInt64], name: str | None = None):
        self.func = func
        self.name = name or func.__name__


@typing.overload
def logicsig(sub: Callable[[], bool | algopy.UInt64], /) -> LogicSig: ...


@typing.overload
def logicsig(*, name: str) -> Callable[[Callable[[], bool | algopy.UInt64]], LogicSig]: ...


def logicsig(
    sub: Callable[[], bool | algopy.UInt64] | None = None, *, name: str | None = None
) -> algopy.LogicSig | Callable[[Callable[[], bool | algopy.UInt64]], LogicSig]:
    """Decorator to indicate a function is a logic signature"""
    import algopy

    def decorator(func: Callable[[], bool | algopy.UInt64]) -> algopy.LogicSig:
        @wraps(func)
        def wrapper() -> bool | algopy.UInt64:
            return func()

        return algopy.LogicSig(wrapper, name=name)

    if sub is None:
        return decorator
    else:
        return decorator(sub)
