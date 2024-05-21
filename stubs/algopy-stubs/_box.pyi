import typing

from algopy import Bytes, UInt64, String

_TKey = typing.TypeVar("_TKey")
_TValue = typing.TypeVar("_TValue")

class Box(typing.Generic[_TValue]):
    """
    Box abstracts the reading and writing of a single value to a single box.
    The box size will be reconfigured dynamically to fit the size of the value being assigned to
    it.
    """

    # TODO: ensure default key works, ensure str/String work
    def __init__(
        self, type_: type[_TValue], /, *, key: bytes | str | Bytes | String = ...
    ) -> None: ...
    def __bool__(self) -> bool:
        """
        Returns True if the box exists, regardless of the truthiness of the contents
        of the box
        """

    @property
    def value(self) -> _TValue:
        """Retrieve the contents of the box. Fails if the box has not been created."""

    @value.setter
    def value(self, value: _TValue) -> None:
        """Write _value_ to the box. Creates the box if it does not exist."""

    @value.deleter
    def value(self) -> None:
        """Delete the box"""

    def get(self, *, default: _TValue) -> _TValue:
        """
        Retrieve the contents of the box, or return the default value if the box has not been
        created.
        @param default: The default value to return if the box has not been created
        """

    def maybe(self) -> tuple[_TValue, bool]:
        """
        Retrieve the contents of the box if it exists, and return a boolean indicating if the box
        exists.

        """

    @property
    def length(self) -> UInt64:
        """
        Get the length of this Box. Fails if the box does not exist
        """

class BoxRef:
    """
    BoxRef abstracts the reading and writing of boxes containing raw binary data. The size is
    configured manually, and can be set to values larger than what the AVM can handle in a single
    value.
    """

    # TODO: ensure default key works, ensure str/String work
    def __init__(self, /, *, key: bytes | str | Bytes | String = ...) -> None: ...
    def __bool__(self) -> bool:
        """Returns True if the box has a value set, regardless of the truthiness of that value"""

    def create(self, *, size: UInt64 | int) -> bool:
        """
        Creates a box with the specified size, setting all bits to zero. Fails if the box already
        exists with a different size. Fails if the specified size is greater than the max box size
        (32,768)

        Returns True if the box was created, False if the box already existed
        """

    def delete(self) -> bool:
        """
        Deletes the box if it exists and returns a value indicating if the box existed
        """

    def extract(self, start_index: UInt64 | int, length: UInt64 | int) -> Bytes:
        """
        Extract a slice of bytes from the box.

        Fails if the box does not exist, or if `start_index + length > len(box)`
        @param start_index: The offset to start extracting bytes from
        @param length: The number of bytes to extract
        @return:
        """

    def resize(self, new_size: UInt64 | int) -> None:
        """
        Resizes the box the specified `new_size`. Truncating existing data if the new value is
        shorter or padding with zero bytes if it is longer.
        @param new_size: The new size of the box
        @return:
        """

    def replace(self, start_index: UInt64 | int, value: Bytes) -> None:
        """
        Write `value` to the box starting at `start_index`. Fails if the box does not exist,
        or if `start_index + len(value) > len(box)`
        @param start_index: The offset to start writing bytes from
        @param value: The bytes to be written
        """

    def splice(self, start_index: UInt64 | int, length: UInt64 | int, value: Bytes) -> None:
        """
        set box to contain its previous bytes up to index `start_index`, followed by `bytes`,
        followed by the original bytes of the box that began at index `start_index + length`

        **Important: This op does not resize the box**
        If the new value is longer than the box size, it will be truncated.
        If the new value is shorter than the box size, it will be padded with zero bytes

        @param start_index: The index to start inserting `value`
        @param length: The number of bytes after `start_index` to omit from the new value
        @param value: The `value` to be inserted.
        """

    def get(self, *, default: Bytes) -> Bytes:
        """
        Retrieve the contents of the box, or return the default value if the box has not been
        created.
        @param default: The default value to return if the box has not been created
        """

    def put(self, value: Bytes) -> None:
        """
        Replaces the contents of box with value. Fails if box exists and len(box) != len(value).
        Creates box if it does not exist
        @param value: The value to write to the box
        """

    def maybe(self) -> tuple[Bytes, bool]:
        """
        Retrieve the contents of the box if it exists, and return a boolean indicating if the box
        exists.
        """

    @property
    def length(self) -> UInt64:
        """
        Get the length of this Box. Fails if the box does not exist
        """

class BoxMap(typing.Generic[_TKey, _TValue]):
    """
    BoxMap abstracts the reading and writing of a set of boxes using a common key and content type.
    Each composite key (prefix + key) still needs to be made available to the application via the
    `boxes` property of the Transaction.
    """

    # TODO: ensure default key_prefix works, ensure str/String work
    def __init__(
        self,
        key_type: type[_TKey],
        value_type: type[_TValue],
        /,
        *,
        key_prefix: bytes | str | Bytes | String = ...,
    ) -> None: ...
    def __getitem__(self, key: _TKey) -> _TValue:
        """
        Retrieve the contents of a keyed box. Fails if the box for the key has not been created.
        """

    def __setitem__(self, key: _TKey, value: _TValue) -> None:
        """Write _value_ to a keyed box. Creates the box if it does not exist"""

    def __delitem__(self, key: _TKey) -> None:
        """Deletes a keyed box"""

    def __contains__(self, key: _TKey) -> bool:
        """
        Returns True if a box with the specified key exists in the map, regardless of the
        truthiness of the contents of the box
        """

    def get(self, key: _TKey, *, default: _TValue) -> _TValue:
        """
        Retrieve the contents of a keyed box, or return the default value if the box has not been
        created.
        @param key: The key of the box to get
        @param default: The default value to return if the box has not been created.
        """

    def maybe(self, key: _TKey) -> tuple[_TValue, bool]:
        """
        Retrieve the contents of a keyed box if it exists, and return a boolean indicating if the
        box exists.
        @param key: The key of the box to get
        """

    def length(self, key: _TKey) -> UInt64:
        """
        Get the length of an item in this BoxMap. Fails if the box does not exist

        @param key: The key of the box to get
        """
