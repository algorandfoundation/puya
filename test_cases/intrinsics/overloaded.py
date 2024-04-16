from algopy import Contract, GlobalState, UInt64, op


class Overloaded(Contract):
    def __init__(self) -> None:
        self.key = GlobalState(UInt64(0))

    def approval_program(self) -> bool:
        assert op.AppGlobal.get_uint64(b"key") == op.AppGlobal.get_uint64(b"key")
        assert self.key.maybe()[0] == self.key.maybe()[0]
        assert op.setbit_uint64(0, 0, 1) == op.setbit_uint64(0, 0, 1)
        assert op.select_uint64(0, 1, True) == op.select_uint64(1, 0, False)
        return True

    def clear_state_program(self) -> bool:
        return True
