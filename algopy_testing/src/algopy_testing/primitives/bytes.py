from __future__ import annotations

import base64
import operator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


from itertools import zip_longest

from algopy_testing.constants import MAX_BYTES_SIZE
from algopy_testing.primitives.uint64 import UInt64
from algopy_testing.utils import as_bytes, as_int64

# TypeError, ValueError are used for operations that are compile time errors
# ArithmeticError and subclasses are used for operations that would fail during AVM execution


class Bytes:
    """
    A python implementation of an AVM []byte
    """

    value: bytes  # underlying bytes value representing the []byte

    def __init__(self, value: bytes = b"") -> None:
        self.value = as_bytes(value)

    def __repr__(self) -> str:
        return repr(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __add__(self, other: Bytes | bytes) -> Bytes:
        """Concatenate Bytes with another Bytes or bytes literal
        e.g. `Bytes(b"Hello ") + b"World"`."""
        if isinstance(other, Bytes):
            return _checked_result(self.value + other.value, "+")
        else:
            result = self.value + as_bytes(other)
            return _checked_result(result, "+")

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
        if isinstance(index, slice):
            return Bytes(self.value[index])
        else:
            int_index = as_int64(index)
            # my_bytes[0:1] => b'j' whereas my_bytes[0] => 106
            return Bytes(self.value[slice(int_index, int_index + 1)])

    def __eq__(self, other: object) -> bool:
        return self.value == as_bytes(other)

    def __and__(self, other: bytes | Bytes) -> Bytes:
        return self._operate_bitwise(other, "and_")

    def __rand__(self, other: bytes) -> Bytes:
        return self & other

    def __or__(self, other: bytes | Bytes) -> Bytes:
        return self._operate_bitwise(other, "or_")

    def __ror__(self, other: bytes) -> Bytes:
        return self | other

    def __xor__(self, other: bytes | Bytes) -> Bytes:
        return self._operate_bitwise(other, "xor")

    def __rxor__(self, other: bytes) -> Bytes:
        return self ^ other

    def __invert__(self) -> Bytes:
        """
        Compute the bitwise inversion of the Bytes.

        Returns:
            Bytes: The result of the bitwise inversion operation.
        """
        return Bytes(bytes(~x + 256 for x in self.value))

    def _operate_bitwise(self, other: bytes | Bytes, operator_name: str) -> Bytes:
        op = getattr(operator, operator_name)
        maybe_bytes = as_bytes(other)
        # pad the shorter of self.value and other bytes with leading zero
        # by reversing them as zip_longest fills at the end
        return Bytes(
            bytes(
                reversed(
                    bytes(
                        op(a[0], a[1])
                        for a in zip_longest(
                            reversed(self.value), reversed(maybe_bytes), fillvalue=0
                        )
                    )
                )
            )
        )

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


def _checked_result(result: bytes, op: str) -> Bytes:
    """Ensures `result` is a valid Bytes value

    Raises:
        ArithmeticError: If `result` of `op` is out of bounds"""
    if len(result) > MAX_BYTES_SIZE:
        raise OverflowError(f"{op} overflows")
    return Bytes(result)
