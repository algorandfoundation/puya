from algopy import Contract, Txn, UInt64, subroutine


class RuntimeDominance(Contract):
    def approval_program(self) -> bool:
        assert runtime_dominance(True) == 2
        assert runtime_dominance(False) == 42
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def runtime_dominance(cond: bool) -> UInt64:
    if cond:
        x = UInt64(1)
    assert Txn.num_app_args == 0
    if cond:
        y = x + 1
    else:
        y = UInt64(42)
    return y
