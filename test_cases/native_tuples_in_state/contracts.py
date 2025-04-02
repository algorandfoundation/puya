from algopy import ARC4Contract, GlobalState, UInt64, arc4


class TuplesInGlobalState(ARC4Contract):
    def __init__(self) -> None:
        self.bare_state = (UInt64(1), UInt64(2))
        self.proxy_obj = GlobalState(tuple[UInt64, UInt64])

    @arc4.abimethod
    def read_values(self) -> tuple[UInt64, UInt64, UInt64, UInt64]:
        a, b = self.bare_state
        c, d = self.proxy_obj.value

        return a, b, c, d
