from algopy import BaseContract, UInt64


class UInt64AddOverflow(BaseContract):
    def approval_program(self) -> bool:
        assert UInt64(2**64 - 1) + 1 > 0
        return True

    def clear_state_program(self) -> bool:
        return True


class UInt64MulOverflow(BaseContract):
    def approval_program(self) -> bool:
        assert UInt64(4294967296) * 8589934592 > 0
        return True

    def clear_state_program(self) -> bool:
        return True


class UInt64ExpOverflow(BaseContract):
    def approval_program(self) -> bool:
        assert UInt64(2) ** 64 > 0
        return True

    def clear_state_program(self) -> bool:
        return True
