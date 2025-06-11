import typing

from algopy import (
    Account,
    Application,
    Box,
    FixedArray,
    Global,
    NativeArray,
    Struct,
    Txn,
    UInt64,
    arc4,
    subroutine,
    urange,
)


class NamedTup(Struct, frozen=True):
    a: UInt64
    b: UInt64


class TupBag(Struct):
    count: UInt64
    items: FixedArray[NamedTup, typing.Literal[8]]
    owner: Account
    app: Application
    too_big: FixedArray[arc4.Byte, typing.Literal[4096]]
    bootstrapped: bool


class Case2WithImmStruct(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.tup_bag = Box(TupBag)

    @arc4.abimethod()
    def create_box(self) -> None:
        assert self.tup_bag.create(), "box already exists"
        self.tup_bag.value.owner = Txn.sender
        self.tup_bag.value.app = Global.current_application_id
        self.tup_bag.value.bootstrapped = True

    @arc4.abimethod()
    def num_tups(self) -> UInt64:
        return self.tup_bag.value.count

    @arc4.abimethod()
    def add_tup(self, tup: NamedTup) -> None:
        self._check_owner()
        assert self.tup_bag.value.count < self.tup_bag.value.items.length, "too many tups"
        self.tup_bag.value.items[self.tup_bag.value.count] = tup
        self.tup_bag.value.count += 1

    @arc4.abimethod()
    def get_tup(self, index: UInt64) -> NamedTup:
        assert index < self.tup_bag.value.count, "index out of bounds"
        return self.tup_bag.value.items[index]

    @arc4.abimethod()
    def sum(self) -> UInt64:
        total = UInt64()
        for i in urange(self.tup_bag.value.count):
            tup = self.tup_bag.value.items[i]
            total += tup.a
            total += tup.b
        return total

    @arc4.abimethod()
    def add_many_tups(self, tups: NativeArray[NamedTup]) -> None:
        for tup in tups:
            self.add_tup(tup)

    @arc4.abimethod()
    def add_fixed_tups(self, tups: FixedArray[NamedTup, typing.Literal[3]]) -> None:
        for tup in tups:
            self.add_tup(tup)

    @arc4.abimethod()
    def set_a(self, a: UInt64) -> None:
        self._check_owner()
        for i in urange(self.tup_bag.value.count):
            tup = self.tup_bag.value.items[i]
            self.tup_bag.value.items[i] = tup._replace(a=a)

    @arc4.abimethod()
    def set_b(self, b: UInt64) -> None:
        self._check_owner()
        for i in urange(self.tup_bag.value.count):
            tup = self.tup_bag.value.items[i]
            self.tup_bag.value.items[i] = tup._replace(b=b)

    @arc4.abimethod()
    def get_3_tups(self, start: UInt64) -> FixedArray[NamedTup, typing.Literal[3]]:
        assert self.tup_bag.value.count >= start + 3, "not enough items"
        items = self.tup_bag.value.items.copy()

        return FixedArray[NamedTup, typing.Literal[3]](
            (
                items[start],
                items[start + 1],
                items[start + 2],
            )
        )

    @arc4.abimethod()
    def get_all_tups(self) -> NativeArray[NamedTup]:
        result = NativeArray[NamedTup]()
        items = self.tup_bag.value.items.copy()
        # TODO: improve this once slicing is supported
        for i in urange(self.tup_bag.value.count):
            result.append(items[i])
        return result

    @subroutine
    def _check_owner(self) -> None:
        assert self.tup_bag.value.bootstrapped, "app not bootstrapped"
        assert self.tup_bag.value.owner == Txn.sender, "sender not authorized"
        assert (
            self.tup_bag.value.app == Global.current_application_id
        ), "this error should be impossible"
