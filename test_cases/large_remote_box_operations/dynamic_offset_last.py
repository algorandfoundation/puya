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
    pad2: LargeBytes
    nested: Parent


@subroutine
def _box(app: Application) -> Box[DynamicOffsets, Remote]:
    return Box.remote(DynamicOffsets, app=app, key=b"box")


class RemoteDynamicOffsetLast(ARC4Contract, avm_version=13):
    @public
    def bootstrap(self, app: Application) -> None:
        _box(app).value = DynamicOffsets(
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
        _box(app).value.pad1.append(Bytes4096())
        self.verify(app, ArrayU64())

    @public
    def concat(self, app: Application, array: ArrayU64) -> None:
        _box(app).value.nested.nested.arr.extend(array)

    @public
    def append(self, app: Application, value: UInt64) -> None:
        _box(app).value.nested.nested.arr.append(value)

    @public
    def pop(self, app: Application) -> UInt64:
        return _box(app).value.nested.nested.arr.pop()

    @public
    def verify(self, app: Application, expected: ArrayU64) -> None:
        assert _box(app).value.nested.baz == 1
        assert _box(app).value.nested.nested.foo == 2
        assert _box(app).value.nested.nested.bar == 3
        assert _box(app).value.nested.buz == 4
        assert _box(app).value.nested.nested.arr == expected
        assert _box(app).value.pad1.length == 1
        assert _box(app).value.pad2.length == 0
        assert _box(app).length > 4096, "expected box length >4096"

    @public
    def get(self, app: Application, idx: UInt64) -> UInt64:
        return _box(app).value.nested.nested.arr[idx]

    @public
    def set(self, app: Application, idx: UInt64, value: UInt64) -> None:
        _box(app).value.nested.nested.arr[idx] = value
