import typing

from algopy import ARC4Contract, Array, Box, FixedBytes, UInt64, public, urange

ArrayU64 = Array[UInt64]
Bytes4096: typing.TypeAlias = FixedBytes[typing.Literal[4096]]
LargeBytes = Array[Bytes4096]


class ArrayUInt64(ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(ArrayU64)

    @public
    def bootstrap(self) -> None:
        self.box.value = ArrayU64()

    @public
    def append(self, value: UInt64) -> None:
        self.box.value.append(value)

    @public
    def concat(self, array: ArrayU64) -> None:
        self.box.value.extend(array)

    @public
    def pop(self) -> UInt64:
        return self.box.value.pop()

    @public
    def get(self, idx: UInt64) -> UInt64:
        return self.box.value[idx]

    @public
    def set(self, idx: UInt64, value: UInt64) -> None:
        self.box.value[idx] = value

    @public
    def verify(self, expected: ArrayU64) -> None:
        # rather than asserting box.value directly (which would attempt to load the whole box)
        # assert the length and individual items
        assert self.box.value.length == expected.length
        for i in urange(expected.length):
            assert self.box.value[i] == expected[i]
