import typing
from collections.abc import Iterable, Iterator, Reversible, Sequence

import algopy

T = typing.TypeVar("T")

class Array(typing.Generic[T], Reversible[T]):
    """A dynamically sized array of the specified type"""

    def __init__(self, *items: T):
        """Initializes a new array with items provided"""

    def __iter__(self) -> Iterator[T]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> Iterator[T]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    @property
    def bytes(self) -> algopy.Bytes:
        """Returns a copy of the underlying bytes of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> T:
        """Gets the item of the array at provided index"""

    def __setitem__(self, index: algopy.UInt64 | int, value: T) -> T:
        """Sets the item of the array at specified index to provided value"""

    def append(self, item: T, /) -> None:
        """Append an item to this array"""

    def extend(
        self,
        other: Iterable[T],
        /,
    ) -> None:
        """Extend this array with the contents of another array"""

    def __add__(
        self,
        other: Sequence[T],
    ) -> Array[T]:
        """Concat two arrays together, returning a new array"""

    def pop(self) -> T:
        """Remove and return the last item of this array"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""
