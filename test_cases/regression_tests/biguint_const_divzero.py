from algopy import BaseContract, BigUInt


class BigUIntConstDivZero(BaseContract):
    """Regression test: compiler crashes with ZeroDivisionError when
    attempting to constant-fold a BigUInt floor division by zero."""

    def approval_program(self) -> bool:
        assert BigUInt(3) // 0 == 1
        return True

    def clear_state_program(self) -> bool:
        return True
