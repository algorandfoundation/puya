import typing
from collections.abc import Callable


class ARC4Contract:
    pass


_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def abimethod(
    fn: Callable[_P, _R] | None = None,
    /,
    **kwargs: object,
) -> (
    Callable[_P, _R]
    | Callable[
        [Callable[_P, _R]],
        Callable[_P, _R],
    ]
):
    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return func(*args, **kwargs)

        return wrapped

    if callable(fn):
        return decorator(fn)

    return decorator
