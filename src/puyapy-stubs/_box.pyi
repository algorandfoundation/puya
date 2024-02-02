from typing import Generic, TypeAlias, TypeVar, overload

from puyapy import Bytes, UInt64

_T = TypeVar("_T")
_TKey = TypeVar("_TKey")

BytesOrString: TypeAlias = Bytes | bytes | str

class Box(Generic[_T]):
    def __init__(
        self,
        type_: type[_T],
        /,
        *,
        key: BytesOrString | None = None,
        description: BytesOrString | None = None,
    ) -> None: ...
    @property
    def value(self) -> _T: ...
    @value.setter
    def value(self, value: _T) -> None: ...
    @value.deleter
    def value(self) -> None: ...
    def __bool__(self) -> bool:
        """Returns True if the box has a value set, regardless of the truthiness of that value"""
    def get(self, default: _T) -> _T: ...
    def maybe(self) -> tuple[_T, bool]: ...
    def length(self) -> tuple[UInt64, bool]:
        """
        Get the length of this Box

        @return A tuple of the box length (or 0 if the box does not exist) and a boolean indicating if the box exists
        """
    def extract_bytes(self, start: UInt64 | int, length: UInt64 | int) -> Bytes:
        """
        Extract bytes from this box
        @param start: Where to start extracting bytes
        @param length: How many bytes to extract

        Errors if start + length > len(box)
        """
    def replace_bytes(self, start: UInt64 | int, bytes_: Bytes) -> None:
        """
        Replace bytes in this box
        @param start: Where to start replacing bytes
        @param bytes_: The replacement bytes

        Errors if start + len(bytes_) > len(box)
        """

class BoxMap(Generic[_TKey, _T]):
    def __init__(
        self,
        key_type: type[_TKey],
        type_: type[_T],
        /,
        *,
        key_prefix: BytesOrString | None = None,
        description: BytesOrString | None = None,
    ) -> None: ...
    def __getitem__(self, key: _TKey) -> _T: ...
    def __setitem__(self, key: _TKey, value: _T) -> None: ...
    def __delitem__(self, key: _TKey) -> None: ...
    def __contains__(self, key: _TKey) -> bool: ...
    def get(self, key: _TKey, default: _T) -> _T: ...
    def maybe(self, key: _TKey) -> tuple[_T, bool]: ...
    def length(self, key: _TKey) -> tuple[UInt64, bool]:
        """
        Get the length of an item in this BoxMap

        @param key: The key for an item in this BoxMap
        @return A tuple of the item length (or 0 if the item does not exist) and a boolean indicating if the item exists
        """
    def extract_bytes(self, key: _TKey, start: UInt64 | int, length: UInt64 | int) -> Bytes:
        """
        Extract bytes from this box
        @param key: The key for an item in this BoxMap
        @param start: Where to start extracting bytes
        @param length: How many bytes to extract

        Errors if start + length > len(box)
        """
    def replace_bytes(self, key: _TKey, start: UInt64 | int, bytes_: Bytes) -> None:
        """
        Replace bytes in this box
        @param key: The key for an item in the BoxMap
        @param start: Where to start replacing bytes
        @param bytes_: The replacement bytes

        Errors if start + len(bytes_) > len(box)
        """
