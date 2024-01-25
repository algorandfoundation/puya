"""
Unfortunately common Python builtins are either typed to produce int (like range),
or go even further and actually require the type to be explicitly int at runtime (like len).

These are their replacements.
"""

from collections.abc import Iterable, Iterator, Reversible
from typing import TypeVar, overload

from puyapy import UInt64

class urange(Reversible[UInt64]):
    @overload
    def __init__(self, stop: int | UInt64, /) -> None: ...
    @overload
    def __init__(self, start: int | UInt64, stop: int | UInt64, /) -> None: ...
    @overload
    def __init__(self, start: int | UInt64, stop: int | UInt64, step: int | UInt64, /) -> None: ...
    def __iter__(self) -> Iterator[UInt64]: ...
    def __reversed__(self) -> Iterator[UInt64]: ...

_T = TypeVar("_T")

def uenumerate(iterable: Iterable[_T]) -> Reversible[tuple[UInt64, _T]]: ...
