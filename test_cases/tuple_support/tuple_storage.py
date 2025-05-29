import typing

from algopy import Box, GlobalState, LocalState, Txn, UInt64, arc4


class TupleWithMutable(typing.NamedTuple):
    arr: arc4.DynamicArray[arc4.UInt64]
    bar: UInt64


class NestedTuplesStorage(arc4.ARC4Contract):
    def __init__(self) -> None:
        self.box = Box(TupleWithMutable)
        self.glob = GlobalState(TupleWithMutable)
        self.loc = LocalState(TupleWithMutable)
        self.tup = TupleWithMutable(
            arr=arc4.DynamicArray(arc4.UInt64(0)),
            bar=UInt64(),
        )
        self.glob.value = self.tup._replace(arr=arc4.DynamicArray(arc4.UInt64(0)))
        self.tup = self.tup._replace(arr=arc4.DynamicArray(arc4.UInt64(0)))

    @arc4.abimethod(allow_actions=["OptIn"])
    def bootstrap(self) -> None:
        self.box.value = self.tup._replace(arr=arc4.DynamicArray(arc4.UInt64(0)))
        self.loc[Txn.sender] = self.tup._replace(arr=arc4.DynamicArray(arc4.UInt64(0)))

    @arc4.abimethod()
    def mutate_tuple(self, val: arc4.UInt64) -> None:
        self.tup.arr.append(val)

    @arc4.abimethod()
    def mutate_box(self, val: arc4.UInt64) -> None:
        self.box.value.arr.append(val)

    @arc4.abimethod()
    def mutate_global(self, val: arc4.UInt64) -> None:
        self.glob.value.arr.append(val)

    @arc4.abimethod()
    def mutate_local(self, val: arc4.UInt64) -> None:
        self.loc[Txn.sender].arr.append(val)
