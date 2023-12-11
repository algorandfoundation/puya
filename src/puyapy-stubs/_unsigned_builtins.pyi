"""
Unfortunately common Python builtins are either typed to produce int (like range),
or go even further and actually require the type to be explicitly int at runtime (like len).

These are their replacements.
"""

from collections.abc import Iterable, Iterator
from typing import TypeVar, overload

from puyapy import UInt64

@overload
def urange(__stop: int | UInt64) -> Iterator[UInt64]: ...
@overload
def urange(
    __start: int | UInt64, __stop: int | UInt64, __step: int | UInt64 = ...
) -> Iterator[UInt64]: ...

_T = TypeVar("_T")

def uenumerate(iterable: Iterable[_T]) -> Iterator[tuple[UInt64, _T]]: ...
