from algopy import Contract, GlobalState, UInt64


class UnobservedWriteStaleRead(Contract):
    """Regression test: three or more consecutive writes to the same key, followed
    immediately by a read of that key. The dead writes are eliminated, and the read is
    forwarded from the write cache. The forwarded value should come from the surviving
    (final) write, but it comes from the write prior.
    This was because the ops list would be modified during iteration, and so any write
    right after a write triggering an elimination would be skipped"""

    def __init__(self) -> None:
        self.stored = GlobalState(UInt64(0))

    def approval_program(self) -> bool:
        self.stored.value = UInt64(33)  # dead
        self.stored.value = UInt64(22)  # dead
        self.stored.value = UInt64(11)  # live
        assert self.stored.value == 11, "stored should be 11"
        return True

    def clear_state_program(self) -> bool:
        return True
