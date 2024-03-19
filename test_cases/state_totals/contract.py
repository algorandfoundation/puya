from puyapy import Bytes, GlobalState, LocalState, StateTotals, UInt64, arc4

GLOBAL_UINTS = 3


class Contract(
    arc4.ARC4Contract,
    state_totals=StateTotals(local_bytes=1, global_uints=GLOBAL_UINTS),
):
    def __init__(self) -> None:
        self.local_one = LocalState(UInt64)
        self.global_one = GlobalState(Bytes)

    @arc4.baremethod(create=True)
    def create(self) -> None:
        pass
