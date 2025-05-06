from algopy import (
    Account,
    ARC4Contract,
    BoxMap,
    Bytes,
    GlobalState,
    LocalState,
    StateTotals,
    Txn,
    UInt64,
    arc4,
    log,
    subroutine,
)


class StateProxyContract(ARC4Contract, state_totals=StateTotals(global_uints=3)):
    def __init__(self) -> None:
        self.local1 = LocalState(UInt64, key="l1", description="l1 description")
        self.local2 = LocalState[UInt64](UInt64, key=b"l2", description="l2 description")
        self.global1 = GlobalState(UInt64, key="g1", description="g1 description")
        self.global2 = GlobalState[UInt64](UInt64(0), key=b"g2", description="g2 description")
        funky_town = (
            GlobalState(UInt64, key="funky")
            if Txn.num_app_args
            else GlobalState(UInt64, key="town")
        )
        funky_town.value = UInt64(123)
        self.box_map = BoxMap(Bytes, UInt64)

    @arc4.abimethod(allow_actions=["OptIn"], create="require")
    def create(self) -> None:
        self.global1.value = UInt64(1)
        self.local1[Txn.sender] = UInt64(2)
        self.local2[Txn.sender] = UInt64(3)

    @arc4.abimethod()
    def clear(self) -> None:
        del self.global1.value
        del self.local1[Txn.sender]
        del self.local2[Txn.sender]
        del self.box_map[get_key()]

    @arc4.abimethod()
    def order_of_eval_global(self) -> None:
        val = self.global1.get(default=default_value())
        assert val == 42

    @arc4.abimethod()
    def order_of_eval_local(self) -> None:
        val = self.local1.get(get_account(), default=default_value())
        assert val == 42

    @arc4.abimethod()
    def order_of_eval_box(self) -> None:
        val = self.box_map.get(get_key(), default=default_value())
        assert val == 42


@subroutine(inline=False)
def get_key() -> Bytes:
    log("key")
    return Bytes(b"box")


@subroutine(inline=False)
def get_account() -> Account:
    log("account")
    return Txn.sender


@subroutine(inline=False)
def default_value() -> UInt64:
    log("default")
    return UInt64(42)
