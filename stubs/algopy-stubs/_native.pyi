import typing
from collections.abc import Iterable, Iterator, Reversible

import algopy

_TArrayItem = typing.TypeVar("_TArrayItem")
_TArrayLength = typing.TypeVar("_TArrayLength", bound=int)

class ImmutableFixedArray(
    typing.Generic[_TArrayItem, _TArrayLength],
    Reversible[_TArrayItem],
):
    """An immutable fixed length Array of the specified type and length"""

    def __init__(self, values: Iterable[_TArrayItem]) -> None: ...
    @classmethod
    def full(cls, item: _TArrayItem) -> typing.Self:
        """Initializes a new array, filled with copies of the specified value"""

    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _TArrayItem:
        """Gets the item of the array at the provided index"""

    def replace(self, index: algopy.UInt64 | int, value: _TArrayItem) -> typing.Self:
        """Returns a copy of the array with the item at the specified index replaced with the specified value"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

class FixedArray(
    typing.Generic[_TArrayItem, _TArrayLength],
    Reversible[_TArrayItem],
):
    """A fixed length Array of the specified type and length"""

    def __init__(self, values: Iterable[_TArrayItem]) -> None: ...
    @classmethod
    def full(cls, item: _TArrayItem) -> typing.Self:
        """Initializes a new array, filled with copies of the specified value"""

    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _TArrayItem:
        """Gets the item of the array at the provided index"""

    def __setitem__(self, index: algopy.UInt64 | int, value: _TArrayItem) -> _TArrayItem:
        """Sets the item of the array at the specified index to provided value"""

    def replace(self, index: algopy.UInt64 | int, value: _TArrayItem) -> typing.Self:
        """Returns a copy of the array with the item at the specified index replaced with the specified value"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

    def freeze(self) -> ImmutableFixedArray[_TArrayItem, _TArrayLength]:
        """Returns an immutable copy of this array"""

class ImmutableArray(Reversible[_TArrayItem]):
    """
    An immutable array that supports fixed and dynamically sized immutable elements.
    Modifications are done by returning a new copy of the array with the modifications applied.

    Example:
    ```python
    arr = ImmutableArray[UInt64]()

    arr = arr.append(UInt64(42))
    element = arr[0]
    assert element == 42
    arr = arr.pop()
    ```
    """

    @typing.overload
    def __init__(self) -> None: ...
    @typing.overload
    def __init__(self, values: Iterable[_TArrayItem]):
        """Initializes a new array with items provided"""

    def __iter__(self) -> Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _TArrayItem:
        """Gets the item of the array at provided index"""

    def replace(self, index: algopy.UInt64 | int, value: _TArrayItem) -> typing.Self:
        """Returns a copy of the array with the item at specified index replaced with the specified value"""

    def append(self, item: _TArrayItem, /) -> typing.Self:
        """Return a copy of the array with a another value appended to the end"""

    def __add__(self, other: Iterable[_TArrayItem], /) -> typing.Self:
        """Return a copy of this array extended with the contents of another array"""

    def pop(self) -> typing.Self:
        """Return a copy of this array with the last item removed"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

class ReferenceArray(Reversible[_TArrayItem]):
    """
    A mutable array that supports fixed sized immutable elements. All references to this array
    will see any updates made to it.

    These arrays may use scratch slots if required. If a contract also needs to use scratch slots
    for other purposes then they should be reserved using the `scratch_slots` parameter
    in [`algopy.Contract`](#algopy.Contract),
    [`algopy.arc4.ARC4Contract`](#algopy.arc4.ARC4Contract) or [`algopy.logicsig`](#algopy.logicsig)
    """

    @typing.overload
    def __init__(self) -> None: ...
    @typing.overload
    def __init__(self, values: Iterable[_TArrayItem]):
        """Initializes a new array with items provided"""

    def __iter__(self) -> Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _TArrayItem:
        """Gets the item of the array at provided index"""

    def __setitem__(self, index: algopy.UInt64 | int, value: _TArrayItem) -> _TArrayItem:
        """Sets the item of the array at specified index to provided value"""

    def append(self, item: _TArrayItem, /) -> None:
        """Append an item to this array"""

    def extend(self, other: Iterable[_TArrayItem], /) -> None:
        """Extend this array with the contents of another array"""

    def pop(self) -> _TArrayItem:
        """Remove and return the last item of this array"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

    def freeze(self) -> ImmutableArray[_TArrayItem]:
        """Returns an immutable copy of this array"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

class Array(typing.Generic[_TArrayItem], Reversible[_TArrayItem]):
    """A dynamically sized Array of the specified type"""

    @typing.overload
    def __init__(self) -> None: ...
    @typing.overload
    def __init__(self, values: Iterable[_TArrayItem]) -> None: ...
    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _TArrayItem:
        """Gets the item of the array at provided index"""

    def append(self, item: _TArrayItem, /) -> None:
        """Append an item to this array"""

    def extend(self, other: Iterable[_TArrayItem], /) -> None:
        """Extend this array with the contents of another array"""

    def __setitem__(self, index: algopy.UInt64 | int, value: _TArrayItem) -> _TArrayItem:
        """Sets the item of the array at specified index to provided value"""

    def __add__(self, other: Iterable[_TArrayItem]) -> Array[_TArrayItem]:
        """Concat two arrays together, returning a new array"""

    def pop(self) -> _TArrayItem:
        """Remove and return the last item of this array"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

    def freeze(self) -> ImmutableArray[_TArrayItem]:
        """Returns an immutable copy of this array"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

@typing.dataclass_transform()
class Struct:
    """Base class for Struct types"""

    def __init_subclass__(
        cls,
        *,
        frozen: bool = False,
        kw_only: bool = False,
    ): ...
    def copy(self) -> typing.Self:
        """Create a copy of this struct"""

    def _replace(self, **kwargs: typing.Any) -> typing.Self:  # type: ignore[explicit-any]
        """
        Return a new instance of the struct replacing specified fields with new values.

        Note that any mutable fields must be explicitly copied to avoid aliasing.
        """

def zero_bytes[T](typ: type[T]) -> T:
    """
    Initializes a new value of the specified type, based on it's zero bytes representation.

    Only works for fixed size types that are bytes encoded.
    """
