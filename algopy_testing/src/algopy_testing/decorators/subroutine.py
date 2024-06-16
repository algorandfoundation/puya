from collections.abc import Callable
from typing import ParamSpec, TypeVar

_P = ParamSpec("_P")
_R = TypeVar("_R")


def subroutine(sub: Callable[_P, _R]) -> Callable[_P, _R]:
    return sub
