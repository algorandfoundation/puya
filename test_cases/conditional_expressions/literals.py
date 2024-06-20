from algopy import Contract, UInt64, subroutine


class Literals(Contract):
    def approval_program(self) -> bool:
        self.with_variable_condition(condition=False)
        self.with_variable_condition(condition=True)

        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def with_variable_condition(self, *, condition: bool) -> None:
        x = UInt64(1 if condition else 0)
        assert bool(x) == condition
        assert x == -(-1 if condition else 0)  # test unary op propagation
        y = x + ((1 if condition else 2) - 1)  # test binary op with literal & non-literal
        # TODO(frist): test reverse
        assert y == 1
        maybe = (1 if condition else 0) < y  # test comparison with non-literal
        assert maybe == (not condition)
        assert (1 if condition else 0) != 2  # test comparison with literal
