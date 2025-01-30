import typing
from collections.abc import Iterable, Iterator, Reversible

import algopy

_T = typing.TypeVar("_T")

class ImmutableArray(Reversible[_T]):
    """An immutable array of the specified type, mutations are done by returning a copy
    of the array with the modifications"""

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

    def replace(self, index: algopy.UInt64 | int, value: _T) -> typing.Self:
        """Returns a copy of the array with the item at specified index replaced with the specified value"""

    def append(self, item: _T, /) -> typing.Self:
        """Return a copy of the array with a another value appended to the end"""

    def __add__(self, other: Iterable[_T], /) -> typing.Self:
        """Return a copy of this array extended with the contents of another array"""

    def pop(self) -> typing.Self:
        """Return a copy of this array with the last item removed"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

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

    def freeze(self) -> ImmutableArray[_T]:
        """Returns an immutable copy of this array"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""
