from algopy import Contract, subroutine


class ConditionalExecutionContract(Contract):
    def __init__(self) -> None:
        self.did_execute_a = False
        self.did_execute_b = False

    def approval_program(self) -> bool:
        # 'or' won't execute rhs if lhs is True
        self.func_a(True) or self.func_b(True)
        self.assert_and_reset(
            self.did_execute_a and not self.did_execute_b,
        )

        # 'or' executes rhs if lhs is False
        self.func_a(False) or self.func_b(True)
        self.assert_and_reset(
            self.did_execute_a and self.did_execute_b,
        )

        # 'and' won't execute rhs if lhs is False
        self.func_a(False) and self.func_b(True)
        self.assert_and_reset(
            self.did_execute_a and not self.did_execute_b,
        )

        # 'and' executes rhs if lhs is True
        self.func_a(True) and self.func_b(True)
        self.assert_and_reset(
            self.did_execute_a and self.did_execute_b,
        )

        # Tuples are fully evaluated before indexing is done
        (self.func_a(True), self.func_b(True))[0]
        self.assert_and_reset(
            self.did_execute_a and self.did_execute_b,
        )

        # Ternary condition won't execute <false expr> if condition is True
        self.func_a(True) if self.func_c(True) else self.func_b(True)
        self.assert_and_reset(
            self.did_execute_a and not self.did_execute_b,
        )

        # Ternary condition won't execute <true expr> if condition is False
        self.func_a(True) if self.func_c(False) else self.func_b(True)
        self.assert_and_reset(
            not self.did_execute_a and self.did_execute_b,
        )

        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def assert_and_reset(self, condition: bool) -> None:
        assert condition
        self.did_execute_b = False
        self.did_execute_a = False

    @subroutine
    def func_a(self, ret_val: bool) -> bool:
        self.did_execute_a = True
        return ret_val

    @subroutine
    def func_b(self, ret_val: bool) -> bool:
        self.did_execute_b = True
        return ret_val

    @subroutine
    def func_c(self, ret_val: bool) -> bool:
        return ret_val
