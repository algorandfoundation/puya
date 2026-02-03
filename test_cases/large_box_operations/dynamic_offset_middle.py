import typing

from algopy import ARC4Contract, Array, Box, FixedBytes, Struct, UInt64, public

ArrayU64 = Array[UInt64]
Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


class Child(Struct):
    foo: UInt64
    arr: ArrayU64
    bar: UInt64


class Parent(Struct):
    baz: UInt64
    nested: Child
    buz: UInt64


class DynamicOffsets(Struct):
    pad1: LargeBytes
    nested: Parent
    pad2: LargeBytes


class DynamicOffsetMiddle(ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(DynamicOffsets)

    @public
    def bootstrap(self) -> None:
        self.box.value = DynamicOffsets(
            nested=Parent(
                baz=UInt64(1),
                nested=Child(
                    foo=UInt64(2),
                    arr=ArrayU64(),
                    bar=UInt64(3),
                ),
                buz=UInt64(4),
            ),
            pad1=LargeBytes(),
            pad2=LargeBytes(),
        )
        self.box.value.pad1.append(Bytes4096())
        self.verify(ArrayU64())

    @public
    def concat(self, array: ArrayU64) -> None:
        self.box.value.nested.nested.arr.extend(array)

    @public
    def append(self, value: UInt64) -> None:
        self.box.value.nested.nested.arr.append(value)

    @public
    def pop(self) -> UInt64:
        return self.box.value.nested.nested.arr.pop()

    @public
    def verify(self, expected: ArrayU64) -> None:
        assert self.box.value.nested.baz == 1
        assert self.box.value.nested.nested.foo == 2
        assert self.box.value.nested.nested.bar == 3
        assert self.box.value.nested.buz == 4
        assert self.box.value.nested.nested.arr == expected
        assert self.box.value.pad1.length == 1
        assert self.box.value.pad2.length == 0
        assert self.box.length > 4096, "expected box length >4096"

    @public
    def get(self, idx: UInt64) -> UInt64:
        return self.box.value.nested.nested.arr[idx]

    @public
    def set(self, idx: UInt64, value: UInt64) -> None:
        self.box.value.nested.nested.arr[idx] = value
