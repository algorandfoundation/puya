"""
Unfortunately common Python builtins are either typed to produce int (like range),
or go even further and actually require the type to be explicitly int at runtime (like len).

These are their replacements.
"""

import typing
from collections.abc import Iterable, Iterator, Reversible

from algopy import UInt64

@typing.final
class urange(Reversible[UInt64]):  # noqa: N801
    """Produces a sequence of UInt64 from start (inclusive) to stop (exclusive) by step.

    urange(4) produces 0, 1, 2, 3
    urange(i, j) produces i, i+1, i+2, ..., j-1.
    urange(i, j, 2) produces i, i+2, i+4, ..., i+2n where n is the largest value where i+2n < j
    """

    @typing.overload
    def __init__(self, stop: int | UInt64, /) -> None: ...
    @typing.overload
    def __init__(self, start: int | UInt64, stop: int | UInt64, /) -> None: ...
    @typing.overload
    def __init__(self, start: int | UInt64, stop: int | UInt64, step: int | UInt64, /) -> None: ...
    def __iter__(self) -> Iterator[UInt64]: ...
    def __reversed__(self) -> Iterator[UInt64]: ...

_T = typing.TypeVar("_T")

@typing.final
class uenumerate(Reversible[tuple[UInt64, _T]]):  # noqa: N801
    """Yields pairs containing a count (from zero) and a value yielded by the iterable argument.

    enumerate is useful for obtaining an indexed list:
        (0, seq[0]), (1, seq[1]), (2, seq[2]), ...

    enumerate((a, b, c)) produces (0, a), (1, b), (2, c)
    """

    def __init__(self, iterable: Iterable[_T]): ...
    def __iter__(self) -> Iterator[tuple[UInt64, _T]]: ...
    def __reversed__(self) -> Iterator[tuple[UInt64, _T]]: ...
