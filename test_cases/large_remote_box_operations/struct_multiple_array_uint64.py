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


@subroutine
def _box(app: Application) -> Box[StructWithMultipleArrays, Remote]:
    return Box.remote(StructWithMultipleArrays, app=app, key=b"box")


class RemoteStructMultipleArrayUInt64(ARC4Contract, avm_version=13):
    @public
    def bootstrap(self, app: Application) -> None:
        _box(app).value = StructWithMultipleArrays(
            a=UInt64(1),
            arr1=ArrayU64(),
            arr2=ArrayU64(),
            arr3=ArrayU64(),
            b=UInt64(2),
            padding=LargeBytes(),
        )
        _box(app).value.padding.append(Bytes4096())
        self.verify(app, ArrayU64())

    @public
    def append(self, app: Application, value: UInt64) -> None:
        _box(app).value.arr1.append(value)
        _box(app).value.arr2.append(value + 1)
        _box(app).value.arr3.append(value + 2)

    @public
    def concat(self, app: Application, array: ArrayU64) -> None:
        _box(app).value.arr1.extend(array)
        _box(app).value.arr2.extend(inc_array(array, UInt64(1)))
        _box(app).value.arr3.extend(inc_array(array, UInt64(2)))

    @public
    def pop(self, app: Application) -> UInt64:
        result = _box(app).value.arr1.pop()
        assert _box(app).value.arr2.pop() == result + 1
        assert _box(app).value.arr3.pop() == result + 2
        return result

    @public
    def get(self, app: Application, idx: UInt64) -> UInt64:
        result = _box(app).value.arr1[idx]
        assert _box(app).value.arr2[idx] == result + 1
        assert _box(app).value.arr3[idx] == result + 2
        return result

    @public
    def set(self, app: Application, idx: UInt64, value: UInt64) -> None:
        _box(app).value.arr1[idx] = value
        _box(app).value.arr2[idx] = value + 1
        _box(app).value.arr3[idx] = value + 2

    @public
    def verify(self, app: Application, expected: ArrayU64) -> None:
        ensure_budget(2000)
        assert _box(app).value.arr1 == expected
        assert _box(app).value.arr2 == inc_array(expected, UInt64(1))
        assert _box(app).value.arr3 == inc_array(expected, UInt64(2))
        assert _box(app).value.a == 1
        assert _box(app).value.b == 2
        assert _box(app).value.padding.length == 1
        assert _box(app).length > 4096, "expected box length >4096"


@subroutine
def inc_array(arr: ArrayU64, inc: UInt64) -> ArrayU64:
    new = arr.copy()
    for idx in urange(new.length):
        new[idx] += inc
    return new
