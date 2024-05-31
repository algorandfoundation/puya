from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def abimethod(
    fn: Callable[_P, _R] | None = None,
) -> Callable[_P, _R] | Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    def decorator(fn: Callable[_P, _R]) -> Callable[_P, _R]:
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return fn(*args, **kwargs)

        return wrapped

    if fn is None:
        return decorator
    else:
        return decorator(fn)


class ARC4Contract:
    pass


class String:
    pass
