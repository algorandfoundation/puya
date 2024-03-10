from __future__ import annotations

import typing

from puyapy_mocks._primatives import Bytes

if typing.TYPE_CHECKING:
    from collections.abc import Callable


class UInt64:
    pass


class String:
    __match_value__: str

    def __init__(self, value: str) -> None:
        self.__match_value__ = value

    def __add__(self, other: String | str | bytes | Bytes) -> String:
        if isinstance(other, (bytes, Bytes)):
            other = bytes(other).decode()
        elif isinstance(other, String):
            other = str(other)
        if isinstance(other, str):
            return String(self.__match_value__ + other)
        return NotImplemented

    def __iadd__(self, other: String | str | bytes | Bytes) -> String:  # noqa: PYI034
        return self.__add__(other)

    def __radd__(self, other: String | str | bytes | Bytes) -> String:
        if isinstance(other, (bytes, Bytes)):
            other = bytes(other).decode()
        elif isinstance(other, String):
            other = str(other)
        if isinstance(other, str):
            return String(other + self.__match_value__)
        return NotImplemented

    def __eq__(self, other: String | str) -> bool:  # type: ignore[override]
        if isinstance(other, String):
            other = str(other)
        if isinstance(other, str):
            return self.__match_value__ == other
        return NotImplemented

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return self.__match_value__


_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def abimethod(
    fn: Callable[_P, _R] | None = None,
    /,
    **kwargs: object,
) -> Callable[_P, _R] | Callable[[Callable[_P, _R]], Callable[_P, _R],]:
    print(kwargs)

    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return func(*args, **kwargs)

        return wrapped

    if callable(fn):
        return decorator(fn)

    return decorator


class ARC4Contract:
    pass
