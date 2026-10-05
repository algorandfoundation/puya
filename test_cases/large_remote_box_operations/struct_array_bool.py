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

ArrayBool = Array[bool]
Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


class StructWithArrayBool(Struct):
    padding: LargeBytes
    a: bool
    arr: ArrayBool
    b: bool
    trailing: Array[UInt64]


@subroutine
def _box(app: Application) -> Box[StructWithArrayBool, Remote]:
    return Box.remote(StructWithArrayBool, app=app, key=b"box")


class RemoteStructArrayBoolContract(ARC4Contract, avm_version=13):
    """As the local equivalent, but against a box of another application.

    Dynamic arrays of bool are bit packed, so in-place box operations must work in
    bits rather than bytes, and only update trailing head offsets by the number of
    bytes actually added or removed.

    The bool members either side of the array are not packed with each other (the
    array's head pointer sits between them), so each occupies its own byte and must
    be left undisturbed as the array is resized."""

    @public
    def bootstrap(self, app: Application) -> None:
        _box(app).value = StructWithArrayBool(
            padding=LargeBytes(),
            a=False,
            arr=ArrayBool(),
            b=True,
            trailing=Array[UInt64]((UInt64(42),)),
        )
        _box(app).value.padding.append(Bytes4096())
        self.verify(app, ArrayBool())

    @public
    def append(self, app: Application, value: bool) -> None:
        _box(app).value.arr.append(value)

    @public
    def concat(self, app: Application, array: ArrayBool) -> None:
        _box(app).value.arr.extend(array)

    @public
    def pop(self, app: Application) -> bool:
        return _box(app).value.arr.pop()

    @public
    def get(self, app: Application, idx: UInt64) -> bool:
        return _box(app).value.arr[idx]

    @public
    def set(self, app: Application, idx: UInt64, value: bool) -> None:
        _box(app).value.arr[idx] = value

    @public
    def verify(self, app: Application, expected: ArrayBool) -> None:
        assert _box(app).value.arr == expected
        assert not _box(app).value.a
        assert _box(app).value.b
        assert _box(app).value.padding.length == 1
        assert _box(app).value.trailing == Array[UInt64]((UInt64(42),))

        # padding: 2 tuple head offset + 2 length header + 4096 data = 4100 bytes
        # a: 1 byte bool (can't pack)
        # arr: 2 (offset) + 2 (length) + packed bool data
        # b: 1 byte bool (same as a)
        # trailing: 2 (offset) + 2 (length) + 8 (one uint64) = 12 bytes
        # total bytesize = 4118 + whatever the packed bool data is
        assert _box(app).length == 4118 + (expected.length + 7) // 8, "unexpected box size"
