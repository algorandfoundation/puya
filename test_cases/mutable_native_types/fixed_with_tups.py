import typing

from algopy import (
    Box,
    FixedArray,
    Struct,
    UInt64,
    arc4,
)


class NamedTup(typing.NamedTuple):
    a: UInt64
    b: UInt64


class TupBag(Struct):
    count: UInt64
    items: FixedArray[NamedTup, typing.Literal[8]]


class FixedWithTups(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.tup_bag = Box(TupBag)

    @arc4.abimethod()
    def create_box(self) -> None:
        self.tup_bag.create()

    @arc4.abimethod()
    def num_tups(self) -> UInt64:
        return self.tup_bag.value.count

    @arc4.abimethod()
    def add_tup(self, tup: NamedTup) -> None:
        assert self.tup_bag.value.count < self.tup_bag.value.items.length, "too many tups"
        self.tup_bag.value.items[self.tup_bag.value.count] = tup
        self.tup_bag.value.count += 1

    @arc4.abimethod()
    def get_tup(self, index: UInt64) -> NamedTup:
        assert index < self.tup_bag.value.count, "index out of bounds"
        return self.tup_bag.value.items[index]
