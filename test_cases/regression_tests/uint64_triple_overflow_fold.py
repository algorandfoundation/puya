from algopy import BaseContract, Global


class UInt64TripleAddOverflow(BaseContract):
    def approval_program(self) -> bool:
        x = Global.group_size
        assert x + 10000000000000000000 + 10000000000000000000 > 0
        return True

    def clear_state_program(self) -> bool:
        return True


class UInt64TripleMulOverflow(BaseContract):
    def approval_program(self) -> bool:
        x = Global.group_size
        assert x * 8589934592 * 8589934592 > 0
        return True

    def clear_state_program(self) -> bool:
        return True
