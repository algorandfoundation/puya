from algopy import BigUInt, Contract


class LargeBigUInt(Contract):
    """Regression test: compiler crashes with AssertionError when BigUInt
    constants exceed 64 bytes (e.g. 2**512)."""

    def approval_program(self) -> bool:
        big = BigUInt(2**512 - 1) + 1
        bigger = big + 1
        assert bigger.bytes.length
        return True

    def clear_state_program(self) -> bool:
        return True
