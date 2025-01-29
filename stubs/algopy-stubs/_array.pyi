import typing
from collections.abc import Iterable, Iterator, Reversible

import algopy

_T = typing.TypeVar("_T")

class Array(Reversible[_T]):
    """An array of the specified type"""

    def __init__(self, *items: _T):
        """Initializes a new array with items provided"""

    def __iter__(self) -> Iterator[_T]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> Iterator[_T]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _T:
        """Gets the item of the array at provided index"""

    def __setitem__(self, index: algopy.UInt64 | int, value: _T) -> _T:
        """Sets the item of the array at specified index to provided value"""

    def append(self, item: _T, /) -> None:
        """Append an item to this array"""

    def extend(self, other: Iterable[_T], /) -> None:
        """Extend this array with the contents of another array"""

    def pop(self) -> _T:
        """Remove and return the last item of this array"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""
