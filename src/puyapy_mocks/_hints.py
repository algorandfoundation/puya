import typing
from collections.abc import Callable

_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def subroutine(sub: Callable[_P, _R], /) -> Callable[_P, _R]:
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        return sub(*args, **kwargs)

    return wrapped
