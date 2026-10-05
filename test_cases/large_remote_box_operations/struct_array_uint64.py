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


class StructWithArrayU64(Struct):
    a: UInt64
    arr: ArrayU64
    b: UInt64
    padding: LargeBytes


@subroutine
def _box(app: Application) -> Box[StructWithArrayU64, Remote]:
    return Box.remote(StructWithArrayU64, app=app, key=b"box")


class RemoteStructArrayUInt64(ARC4Contract, avm_version=13):
    @public
    def bootstrap(self, app: Application) -> None:
        _box(app).value = StructWithArrayU64(
            a=UInt64(1),
            arr=ArrayU64(),
            b=UInt64(2),
            padding=LargeBytes(),
        )
        _box(app).value.padding.append(Bytes4096())
        self.verify(app, ArrayU64())

    @public
    def append(self, app: Application, value: UInt64) -> None:
        _box(app).value.arr.append(value)

    @public
    def concat(self, app: Application, array: ArrayU64) -> None:
        _box(app).value.arr.extend(array)

    @public
    def pop(self, app: Application) -> UInt64:
        return _box(app).value.arr.pop()

    @public
    def get(self, app: Application, idx: UInt64) -> UInt64:
        return _box(app).value.arr[idx]

    @public
    def set(self, app: Application, idx: UInt64, value: UInt64) -> None:
        _box(app).value.arr[idx] = value

    @public
    def verify(self, app: Application, expected: ArrayU64) -> None:
        assert _box(app).value.arr == expected
        assert _box(app).value.a == 1
        assert _box(app).value.b == 2
        assert _box(app).value.padding.length == 1
        assert _box(app).length > 4096, "expected box length >4096"
