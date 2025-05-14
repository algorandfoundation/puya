import typing

from algopy import (
    Box,
    FixedArray,
    NativeArray,
    Struct,
    UInt64,
    arc4,
    urange,
)


class NamedTup(Struct):
    a: UInt64
    b: UInt64


class TupBag(Struct):
    count: UInt64
    items: FixedArray[NamedTup, typing.Literal[8]]


class Case3WithStruct(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.tup_bag = Box(TupBag)

    @arc4.abimethod()
    def create_box(self) -> None:
        assert self.tup_bag.create(), "box already existed"

    @arc4.abimethod()
    def num_tups(self) -> UInt64:
        return self.tup_bag.value.count

    @arc4.abimethod()
    def add_tup(self, tup: NamedTup) -> None:
        assert self.tup_bag.value.count < self.tup_bag.value.items.length, "too many tups"
        self.tup_bag.value.items[self.tup_bag.value.count] = tup.copy()
        self.tup_bag.value.count += 1

    @arc4.abimethod()
    def get_tup(self, index: UInt64) -> NamedTup:
        assert index < self.tup_bag.value.count, "index out of bounds"
        return self.tup_bag.value.items[index]

    @arc4.abimethod()
    def sum(self) -> UInt64:
        total = UInt64()
        for i in urange(self.tup_bag.value.count):
            tup = self.tup_bag.value.items[i].copy()
            total += tup.a
            total += tup.b
        return total

    @arc4.abimethod()
    def add_many_tups(self, tups: NativeArray[NamedTup]) -> None:
        for i in urange(tups.length):
            self.add_tup(tups[i].copy())

    @arc4.abimethod()
    def add_fixed_tups(self, tups: FixedArray[NamedTup, typing.Literal[3]]) -> None:
        for i in urange(tups.length):
            self.add_tup(tups[i].copy())

    @arc4.abimethod()
    def set_a(self, a: UInt64) -> None:
        for i in urange(self.tup_bag.value.count):
            self.tup_bag.value.items[i].a = a

    @arc4.abimethod()
    def set_b(self, b: UInt64) -> None:
        for i in urange(self.tup_bag.value.count):
            self.tup_bag.value.items[i].b = b

    @arc4.abimethod()
    def get_3_tups(self, start: UInt64) -> FixedArray[NamedTup, typing.Literal[3]]:
        assert self.tup_bag.value.count >= start + 3, "not enough items"
        items = self.tup_bag.value.items.copy()

        return FixedArray[NamedTup, typing.Literal[3]](
            (
                items[start].copy(),
                items[start + 1].copy(),
                items[start + 2].copy(),
            )
        )
