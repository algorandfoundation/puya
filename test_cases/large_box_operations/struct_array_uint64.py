import typing

from algopy import ARC4Contract, Array, Box, FixedBytes, Struct, UInt64, public

ArrayU64 = Array[UInt64]
Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


class StructWithArrayU64(Struct):
    a: UInt64
    arr: ArrayU64
    b: UInt64
    padding: LargeBytes


class StructArrayUInt64(ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(StructWithArrayU64)

    @public
    def bootstrap(self) -> None:
        self.box.value = StructWithArrayU64(
            a=UInt64(1),
            arr=ArrayU64(),
            b=UInt64(2),
            padding=LargeBytes(),
        )
        self.box.value.padding.append(Bytes4096())
        self.verify(ArrayU64())

    @public
    def append(self, value: UInt64) -> None:
        self.box.value.arr.append(value)

    @public
    def concat(self, array: ArrayU64) -> None:
        self.box.value.arr.extend(array)

    @public
    def pop(self) -> UInt64:
        return self.box.value.arr.pop()

    @public
    def get(self, idx: UInt64) -> UInt64:
        return self.box.value.arr[idx]

    @public
    def set(self, idx: UInt64, value: UInt64) -> None:
        self.box.value.arr[idx] = value

    @public
    def verify(self, expected: ArrayU64) -> None:
        assert self.box.value.arr == expected
        assert self.box.value.a == 1
        assert self.box.value.b == 2
        assert self.box.value.padding.length == 1
        assert self.box.length > 4096, "expected box length >4096"
