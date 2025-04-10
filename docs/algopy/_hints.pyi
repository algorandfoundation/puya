import typing
from collections.abc import Callable

_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")

@typing.overload
def subroutine(sub: Callable[_P, _R], /) -> Callable[_P, _R]: ...
@typing.overload
def subroutine(
    *, inline: bool | typing.Literal["auto"] = "auto"
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """
    Decorator to indicate functions or methods that can be called by a Smart Contract

    Inlining can be controlled with the decorator argument `inline`.
    When unspecified it defaults to auto, which allows the optimizer to decide whether to inline
    or not. Setting `inline=True` forces inlining, and `inline=False` ensures the function will
    never be inlined.
    """
