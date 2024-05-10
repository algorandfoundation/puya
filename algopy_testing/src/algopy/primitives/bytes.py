from __future__ import annotations
import base64

import functools
from typing import Iterator

from src.algopy.primitives.uint64 import UInt64

# TypeError, ValueError are used for operations that are compile time errors
# ArithmeticError and subclasses are used for operations that would fail during AVM execution


@functools.total_ordering
class Bytes:
    """
    A python implementation of an AVM []byte
    """

    value: bytes  # underlying bytes value representing the []byte

    def __init__(self, value: int = 0) -> None:
        self.value = value.to_bytes(8)

    def __init__(self, value: str) -> None:
        self.value = str.encode(value)

    def __init__(self, value: bytes) -> None:
        self.value = value

    def __repr__(self) -> str:
        return repr(bytes)

    def __str__(self) -> str:
        return str(self.value)
    
    def __bool__(self) -> bool:
        return len(self.value) > 0
    
    def __len__(self) -> int:
        return len(self.value)
    
    def __iter__(self) -> Iterator[Bytes]:
        """Bytes can be iterated, yielding each consecutive byte"""
        return _Bytes_iter(self, 1)

    def __reversed__(self) -> Iterator[Bytes]:
        """Bytes can be iterated in reverse, yield each preceding byte starting at the end"""
        return _Bytes_iter(self, -1)
    
    def __getitem__(
        self, index: UInt64 | int | slice
    ) -> Bytes:  # maps to substring/substring3 if slice, extract/extract3 otherwise?
        """Returns a Bytes containing a single byte if indexed with UInt64 or int
        otherwise the substring o bytes described by the slice"""
        # my_bytes[0:1] => b'j' whereas my_bytes[0] => 106        
        return Bytes(self.value[index]) if isinstance(index, slice) else Bytes(self.value[index, index+1])
    
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


class _Bytes_iter:
    value: Bytes

    def __init__(self, sequence: Bytes, step: int=1):
        self.value = sequence
        self.current = 0 if step > 0 else len(sequence) - 1
        self.step = step
        self.myend = len(sequence) - 1 if step > 0 else 0

    def __iter__(self):return self

    def __next__(self) -> Bytes:
        #if current is one step over the end
        if self.current == self.myend+self.step: 
            raise StopIteration
        else:
            self.current+=self.step
            return self.value[self.current-self.step]
