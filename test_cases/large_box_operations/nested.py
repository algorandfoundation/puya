import typing

from algopy import ARC4Contract, Array, Box, FixedBytes, Struct, UInt64, public

Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


class Child(Struct, frozen=True):
    foo: UInt64
    bar: UInt64


class Parent(Struct, frozen=True):
    baz: UInt64
    simple: Child
    buz: UInt64


class GrandParent(Struct):
    a: UInt64
    arr: Array[Parent]
    b: UInt64


class StructWithNestedArray(Struct):
    nested: GrandParent
    padding: LargeBytes


class NestedArrayUInt64(ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(StructWithNestedArray)

    @public
    def bootstrap(self) -> None:
        self.box.value = StructWithNestedArray(
            nested=GrandParent(a=UInt64(1), arr=Array[Parent](), b=UInt64(2)),
            padding=LargeBytes(),
        )
        self.box.value.padding.append(Bytes4096())
        self.verify(Array[Parent]())

    @public
    def append(self, value: Parent) -> None:
        self.box.value.nested.arr.append(value)

    @public
    def concat(self, array: Array[Parent]) -> None:
        self.box.value.nested.arr.extend(array)

    @public
    def pop(self) -> Parent:
        return self.box.value.nested.arr.pop()

    @public
    def get(self, idx: UInt64) -> Parent:
        return self.box.value.nested.arr[idx]

    @public
    def set(self, idx: UInt64, value: Parent) -> None:
        self.box.value.nested.arr[idx] = value

    @public
    def verify(self, expected: Array[Parent]) -> None:
        assert self.box.value.nested.arr == expected
        assert self.box.value.nested.a == 1
        assert self.box.value.nested.b == 2
        assert self.box.value.padding.length == 1
        assert self.box.length > 4096, "expected box length >4096"
