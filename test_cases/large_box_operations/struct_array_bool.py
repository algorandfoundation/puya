import typing

from algopy import ARC4Contract, Array, Box, FixedBytes, Struct, UInt64, public

ArrayBool = Array[bool]
Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


class StructWithArrayBool(Struct):
    padding: LargeBytes
    a: bool
    arr: ArrayBool
    b: bool
    trailing: Array[UInt64]


class StructArrayBoolContract(ARC4Contract):
    """Dynamic arrays of bool are bit packed, so in-place box operations must
    work in bits rather than bytes, and only update trailing head offsets by the
    number of bytes actually added or removed.

    The bool members either side of the array are not packed with each other (the
    array's head pointer sits between them), so each occupies its own byte and must
    be left undisturbed as the array is resized."""

    def __init__(self) -> None:
        self.box = Box(StructWithArrayBool)

    @public
    def bootstrap(self) -> None:
        self.box.value = StructWithArrayBool(
            padding=LargeBytes(),
            a=False,
            arr=ArrayBool(),
            b=True,
            trailing=Array[UInt64]((UInt64(42),)),
        )
        self.box.value.padding.append(Bytes4096())
        self.verify(ArrayBool())

    @public
    def append(self, value: bool) -> None:
        self.box.value.arr.append(value)

    @public
    def concat(self, array: ArrayBool) -> None:
        self.box.value.arr.extend(array)

    @public
    def pop(self) -> bool:
        return self.box.value.arr.pop()

    @public
    def get(self, idx: UInt64) -> bool:
        return self.box.value.arr[idx]

    @public
    def set(self, idx: UInt64, value: bool) -> None:
        self.box.value.arr[idx] = value

    @public
    def verify(self, expected: ArrayBool) -> None:
        assert self.box.value.arr == expected
        assert not self.box.value.a
        assert self.box.value.b
        assert self.box.value.padding.length == 1
        assert self.box.value.trailing == Array[UInt64]((UInt64(42),))

        # padding: 2 tuple head offset + 2 length header + 4096 data = 4100 bytes
        # a: 1 byte bool (can't pack)
        # arr: 2 (offset) + 2 (length) + packed bool data
        # b: 1 byte bool (same as a)
        # trailing: 2 (offset) + 2 (length) + 8 (one uint64) = 12 bytes
        # total bytesize = 4118 + whatever the packed bool data is
        assert self.box.length == 4118 + (expected.length + 7) // 8, "unexpected box size"
