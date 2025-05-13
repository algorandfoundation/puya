import typing

from algopy import Box, Txn, UInt64, arc4

Bytes1024 = arc4.StaticArray[arc4.Byte, typing.Literal[1024]]

UInt64Array = arc4.StaticArray[arc4.UInt64, typing.Literal[128]]


class BoundedArray(arc4.Struct):
    values: UInt64Array
    count: arc4.UInt8


class LargeStruct(arc4.Struct):
    pad1: Bytes1024
    pad2: Bytes1024
    address: arc4.Address
    numbers: BoundedArray
    pad3: Bytes1024


class Contract(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(LargeStruct, key="b")

    @arc4.abimethod()
    def create_box(self) -> None:
        assert self.box.create(), "expected box to be created"

    @arc4.abimethod()
    def update_box(self) -> None:
        # should be able to update box without reading onto stack
        self.box.value.address = arc4.Address(Txn.sender)

    @arc4.abimethod()
    def append(self, value: UInt64) -> None:
        index = self.box.value.numbers.count.native
        self.box.value.numbers.values[index] = arc4.UInt64(value)
        self.box.value.numbers.count = arc4.UInt8(index + 1)

    @arc4.abimethod()
    def box_len(self) -> UInt64:
        return self.box.length

    @arc4.abimethod()
    def box_exists_len(self) -> tuple[bool, UInt64]:
        if self.box:
            return True, self.box.length
        else:
            return False, UInt64()
