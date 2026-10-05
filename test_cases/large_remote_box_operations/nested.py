import typing

from algopy import (
    Application,
    ARC4Contract,
    Array,
    Box,
    FixedBytes,
    Remote,
    Struct,
    UInt64,
    public,
    subroutine,
)

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


@subroutine
def _box(app: Application) -> Box[StructWithNestedArray, Remote]:
    return Box.remote(StructWithNestedArray, app=app, key=b"box")


class RemoteNestedArrayUInt64(ARC4Contract, avm_version=13):
    @public
    def bootstrap(self, app: Application) -> None:
        _box(app).value = StructWithNestedArray(
            nested=GrandParent(a=UInt64(1), arr=Array[Parent](), b=UInt64(2)),
            padding=LargeBytes(),
        )
        _box(app).value.padding.append(Bytes4096())
        self.verify(app, Array[Parent]())

    @public
    def append(self, app: Application, value: Parent) -> None:
        _box(app).value.nested.arr.append(value)

    @public
    def concat(self, app: Application, array: Array[Parent]) -> None:
        _box(app).value.nested.arr.extend(array)

    @public
    def pop(self, app: Application) -> Parent:
        return _box(app).value.nested.arr.pop()

    @public
    def get(self, app: Application, idx: UInt64) -> Parent:
        return _box(app).value.nested.arr[idx]

    @public
    def set(self, app: Application, idx: UInt64, value: Parent) -> None:
        _box(app).value.nested.arr[idx] = value

    @public
    def verify(self, app: Application, expected: Array[Parent]) -> None:
        assert _box(app).value.nested.arr == expected
        assert _box(app).value.nested.a == 1
        assert _box(app).value.nested.b == 2
        assert _box(app).value.padding.length == 1
        assert _box(app).length > 4096, "expected box length >4096"
