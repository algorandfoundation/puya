import typing as t
from collections.abc import Iterable, Sized

from puyapy import UInt64

# words = ["help", "me"]
# AVM:
# offsets = [0,4]
# data = ["h", "e", "l", "p", "m", "e"]
# len offsets => len of words
# constant time access to words[i]
# constant time append, or pop (from end)

# 0x01 = Array
# [0x01, offsets slot ID, data slot ID]

# scratch slot "offsets slot ID" (bytes[]) = [0x0000, 0x0004] # total length = 4 bytes, len(words) = len(offsets) / 2
# scratch slot "data slot ID" (bytes[]) = ["h", "e", "l", "p", "m", "e"]
# mutate individual element: constant time (2x extract, 1x concat)

# class Array(Sized, Iterable):
#     pass

# 0x12 = MyStruct
# [ 0x12, field 1 slot ID, field 2 slot ID]
#
_T = t.TypeVar("_T")

@t.final
class Array(Iterable[_T], Sized):
    def __init__(self, *data: _T) -> None: ...
    def __iter__(self) -> t.Iterator[_T]: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: UInt64 | int) -> _T: ...
    def __setitem__(self, index: UInt64 | int, value: _T) -> None: ...
    def __delitem__(self, index: UInt64 | int) -> None: ...
    def append(self, value: _T) -> None: ...
    def pop(self) -> _T: ...

# fixed size value types: UInt64
# variable sized value types: Bytes (and descendants), BigUInt
# reference types: Array, Struct

# uint_arr = Array(UInt64(1), UInt64(2))
# AVM:
# [0x01,

# class Foo(Struct):
#     x: UInt64
#     y: Bytes
#
# f1 = Foo(UInt64(1), Bytes("abc"))
# f2 = Foo(UInt64(2), Bytes("def"))
# foo_arr = Array(f1, f2)
# OR

#
# foo_arr: [0x01,
