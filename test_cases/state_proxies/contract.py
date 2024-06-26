from algopy import (
    ARC4Contract,
    GlobalState,
    LocalState,
    StateTotals,
    Txn,
    UInt64,
    arc4,
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

    @arc4.abimethod(allow_actions=["OptIn"], create="require")
    def create(self) -> None:
        self.global1.value = UInt64(1)
        self.local1[Txn.sender] = UInt64(2)
        self.local2[Txn.sender] = UInt64(3)
