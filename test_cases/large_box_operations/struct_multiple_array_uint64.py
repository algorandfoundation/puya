import typing

from algopy import (
    ARC4Contract,
    Array,
    Box,
    FixedBytes,
    Struct,
    UInt64,
    ensure_budget,
    public,
    subroutine,
    urange,
)

ArrayU64 = Array[UInt64]
Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


class StructWithMultipleArrays(Struct):
    a: UInt64
    # first dynamic and last dynamic elements have special behaviour
    # so have 3 dynamic arrays to cover all permutations
    arr1: ArrayU64
    arr2: ArrayU64
    arr3: ArrayU64
    b: UInt64
    padding: LargeBytes


class StructMultipleArrayUInt64(ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(StructWithMultipleArrays)

    @public
    def bootstrap(self) -> None:
        self.box.value = StructWithMultipleArrays(
            a=UInt64(1),
            arr1=ArrayU64(),
            arr2=ArrayU64(),
            arr3=ArrayU64(),
            b=UInt64(2),
            padding=LargeBytes(),
        )
        self.box.value.padding.append(Bytes4096())
        self.verify(ArrayU64())

    @public
    def append(self, value: UInt64) -> None:
        self.box.value.arr1.append(value)
        self.box.value.arr2.append(value + 1)
        self.box.value.arr3.append(value + 2)

    @public
    def concat(self, array: ArrayU64) -> None:
        self.box.value.arr1.extend(array)
        self.box.value.arr2.extend(inc_array(array, UInt64(1)))
        self.box.value.arr3.extend(inc_array(array, UInt64(2)))

    @public
    def pop(self) -> UInt64:
        result = self.box.value.arr1.pop()
        assert self.box.value.arr2.pop() == result + 1
        assert self.box.value.arr3.pop() == result + 2
        return result

    @public
    def get(self, idx: UInt64) -> UInt64:
        result = self.box.value.arr1[idx]
        assert self.box.value.arr2[idx] == result + 1
        assert self.box.value.arr3[idx] == result + 2
        return result

    @public
    def set(self, idx: UInt64, value: UInt64) -> None:
        self.box.value.arr1[idx] = value
        self.box.value.arr2[idx] = value + 1
        self.box.value.arr3[idx] = value + 2

    @public
    def verify(self, expected: ArrayU64) -> None:
        ensure_budget(2000)
        assert self.box.value.arr1 == expected
        assert self.box.value.arr2 == inc_array(expected, UInt64(1))
        assert self.box.value.arr3 == inc_array(expected, UInt64(2))
        assert self.box.value.a == 1
        assert self.box.value.b == 2
        assert self.box.value.padding.length == 1
        assert self.box.length > 4096, "expected box length >4096"


@subroutine
def inc_array(arr: ArrayU64, inc: UInt64) -> ArrayU64:
    new = arr.copy()
    for idx in urange(new.length):
        new[idx] += inc
    return new
