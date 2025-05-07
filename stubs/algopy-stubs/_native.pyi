import typing
from collections.abc import Iterable, Reversible
import algopy

_TArrayItem = typing.TypeVar("_TArrayItem")
_TArrayLength = typing.TypeVar("_TArrayLength", bound=int)

class FixedArray(
    typing.Generic[_TArrayItem, _TArrayLength],
    Reversible[_TArrayItem],
):
    """A fixed length Array of the specified type and length"""

    def __init__(self) -> None: ...
    def __iter__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array"""

    def __reversed__(self) -> typing.Iterator[_TArrayItem]:
        """Returns an iterator for the items in the array, in reverse order"""

    @property
    def length(self) -> algopy.UInt64:
        """Returns the current length of the array"""

    def __getitem__(self, index: algopy.UInt64 | int) -> _TArrayItem:
        """Gets the item of the array at provided index"""

    def __setitem__(self, index: algopy.UInt64 | int, value: _TArrayItem) -> _TArrayItem:
        """Sets the item of the array at specified index to provided value"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

# TODO: breaking change
# algopy.Array -> algopy.ReferenceArray
# algopy.NativeArray -> algopy.Array
class NativeArray(typing.Generic[_TArrayItem], Reversible[_TArrayItem]):
    """A dynamically sized Array of the specified type"""

    def __init__(self) -> None: ...
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

    def __add__(self, other: Iterable[_TArrayItem]) -> NativeArray[_TArrayItem]:
        """Concat two arrays together, returning a new array"""

    def pop(self) -> _TArrayItem:
        """Remove and return the last item of this array"""

    def copy(self) -> typing.Self:
        """Create a copy of this array"""

    def __bool__(self) -> bool:
        """Returns `True` if not an empty array"""

@typing.dataclass_transform()
class Struct:
    def __init_subclass__(
        cls,
        *,
        frozen: bool = False,
        kw_only: bool = False,
    ): ...

    """Base class for Struct types"""
    def copy(self) -> typing.Self:
        """Create a copy of this struct"""

    def _replace(self, **kwargs: typing.Any) -> typing.Self:  # type: ignore[misc]
        """Return a new instance of the struct replacing specified fields with new values.

        Note that any mutable fields must be explicitly copied to avoid aliasing."""
