from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

from algopy._constants import MAX_BYTES_SIZE
from algopy.primitives.uint64 import UInt64

# TypeError, ValueError are used for operations that are compile time errors
# ArithmeticError and subclasses are used for operations that would fail during AVM execution


class Bytes:
    """
    A python implementation of an AVM []byte
    """

    value: bytes  # underlying bytes value representing the []byte

    def __init__(self, value: bytes = b"") -> None:
        self.value = _as_bytes(value)

    # @classmethod
    # def from_int(cls, value: int = 0) -> Bytes:
    #     return cls(value.to_bytes(8))

    # @classmethod
    # def from_str(cls, value: str) -> Bytes:
    #     return cls(str.encode(value))

    def __repr__(self) -> str:
        return repr(bytes)

    def __str__(self) -> str:
        return str(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __add__(self, other: Bytes | bytes) -> Bytes:
        """Concatenate Bytes with another Bytes or bytes literal
        e.g. `Bytes(b"Hello ") + b"World"`."""
        return (
            _checked_result(self.value + other.value, "+")
            if isinstance(other, Bytes)
            else _checked_result(self.value + other, "+")
        )

    def __radd__(self, other: bytes) -> Bytes:
        """Concatenate Bytes with another Bytes or bytes literal
        e.g. `b"Hello " + Bytes(b"World")`."""
        return _checked_result(other + self.value, "+")

    def __len__(self) -> int:
        return len(self.value)

    def __iter__(self) -> Iterator[Bytes]:
        """Bytes can be iterated, yielding each consecutive byte"""
        return _BytesIter(self, 1)

    def __reversed__(self) -> Iterator[Bytes]:
        """Bytes can be iterated in reverse, yield each preceding byte starting at the end"""
        return _BytesIter(self, -1)

    def __getitem__(
        self, index: UInt64 | int | slice
    ) -> Bytes:  # maps to substring/substring3 if slice, extract/extract3 otherwise?
        """Returns a Bytes containing a single byte if indexed with UInt64 or int
        otherwise the substring o bytes described by the slice"""
        # my_bytes[0:1] => b'j' whereas my_bytes[0] => 106
        return (
            Bytes(self.value[index])
            if isinstance(index, slice)
            else Bytes(self.value[slice(index, index + 1)])
        )

    def __eq__(self, other: object) -> bool:
        maybe_bytes = _as_maybe_bytes(other)
        # returning NotImplemented here will allow BigUInt to handle larger comparisons
        if maybe_bytes is None:
            return NotImplemented
        return self.value == maybe_bytes

    def __invert__(self) -> Bytes:
        """
        Compute the bitwise inversion of the Bytes.

        Returns:
            Bytes: The result of the bitwise inversion operation.
        """
        return Bytes(bytes(~x + 256 for x in self.value))

    @property
    def length(self) -> UInt64:
        """Returns the length of the Bytes"""
        return UInt64(len(self.value))

    @staticmethod
    def from_base32(value: str) -> Bytes:
        """Creates Bytes from a base32 encoded string e.g. `Bytes.from_base32("74======")`"""
        return Bytes(base64.b32decode(value))

    @staticmethod
    def from_base64(value: str) -> Bytes:
        """Creates Bytes from a base64 encoded string e.g. `Bytes.from_base64("RkY=")`"""
        return Bytes(base64.b64decode(value))

    @staticmethod
    def from_hex(value: str) -> Bytes:
        """Creates Bytes from a hex/octal encoded string e.g. `Bytes.from_hex("FF")`"""
        return Bytes(base64.b16decode(value))


class _BytesIter:
    value: Bytes

    def __init__(self, sequence: Bytes, step: int = 1):
        self.value = sequence
        self.current = 0 if step > 0 else len(sequence) - 1
        self.step = step
        self.myend = len(sequence) - 1 if step > 0 else 0

    def __iter__(self) -> _BytesIter:
        return self

    def __next__(self) -> Bytes:
        # if current is one step over the end
        if self.current == self.myend + self.step:
            raise StopIteration

        self.current += self.step
        return self.value[self.current - self.step]


def _as_maybe_bytes(value: object) -> bytes | None:
    """Returns bytes value if `value` is a bytes or Bytes, otherwise None"""
    match value:
        case bytes(bytes_value):
            return _as_bytes(bytes_value)
        case Bytes(value=bytes_value):
            return bytes_value
        case n if (isinstance(n, Sequence) and all(isinstance(i, int) for i in n)):
            return _as_bytes(n)
        case _:
            return None


def _checked_result(result: bytes, op: str) -> Bytes:
    """Ensures `result` is a valid Bytes value

    Raises:
        ArithmeticError: If `result` of `op` is out of bounds"""
    if len(result) < 0:
        raise ArithmeticError(f"{op} underflows")
    if len(result) > MAX_BYTES_SIZE:
        raise OverflowError(f"{op} overflows")
    return Bytes(result)


def _as_bytes(value: object) -> bytes:
    from algopy.primitives.util import as_bytes

    return as_bytes(value, max_size=MAX_BYTES_SIZE)
