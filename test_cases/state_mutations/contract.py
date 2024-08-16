from algopy import (
    Account,
    ARC4Contract,
    Box,
    BoxMap,
    GlobalState,
    LocalState,
    Txn,
    arc4,
    subroutine,
)


class MyStruct(arc4.Struct):
    bar: arc4.UInt64
    baz: arc4.String


MyArray = arc4.DynamicArray[MyStruct]


class Contract(ARC4Contract):
    def __init__(self) -> None:
        self.glob = GlobalState(MyArray)
        self.loc = LocalState(MyArray)
        self.box = Box(MyArray)
        self.map = BoxMap(Account, MyArray)

    @arc4.baremethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        self.glob.value = MyArray()
        self.box.value = MyArray()
        self.loc[Txn.sender] = MyArray()
        self.map[Txn.sender] = MyArray()

    @arc4.abimethod
    def append(self) -> None:
        struct = get_struct()
        self.glob.value.append(struct.copy())
        self.loc[Txn.sender].append(struct.copy())
        self.box.value.append(struct.copy())
        self.map[Txn.sender].append(struct.copy())

    @arc4.abimethod
    def modify(self) -> None:
        self.glob.value[0].baz = arc4.String("modified")
        self.loc[Txn.sender][0].baz = arc4.String("modified")
        self.box.value[0].baz = arc4.String("modified")
        self.map[Txn.sender][0].baz = arc4.String("modified")

    @arc4.abimethod
    def get(self) -> MyArray:
        a1 = self.glob.value.copy()
        a2 = self.loc[Txn.sender].copy()
        a3 = self.box.value.copy()
        a4 = self.map[Txn.sender].copy()

        assert a1 == a2, "expected local == global"
        assert a1 == a3, "expected box == global"
        assert a1 == a4, "expected map == global"
        return a1


@subroutine
def get_struct() -> MyStruct:
    return MyStruct(
        bar=arc4.UInt64(1),
        baz=arc4.String("baz"),
    )
