from __future__ import annotations

import typing

from algopy_testing.utils import as_int64

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    import algopy


class urange:  # noqa: N801
    _value: range

    def __init__(self, *args: int | algopy.UInt64) -> None:
        self._value = range(*[as_int64(arg) for arg in args])

    def __iter__(self) -> Iterator[algopy.UInt64]:
        import algopy

        return map(algopy.UInt64, self._value)

    def __reversed__(self) -> Iterator[algopy.UInt64]:
        import algopy

        return map(algopy.UInt64, reversed(self._value))


def uenumerate(_iterable: typing.Any) -> typing.Any:
    pass
