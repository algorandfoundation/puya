from algopy import Contract, UInt64, log, subroutine


class PRE(Contract):
    def approval_program(self) -> bool:
        a = UInt64(3)
        b = UInt64(5)
        for cond in (True, False):
            assert test(a, b, cond) == a + b
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test(a: UInt64, b: UInt64, cond: bool) -> UInt64:
    if cond:
        result = a + b
        log("cond: ", result)
    else:
        result = a + b
        log("!cond: ", result)
    assert result == (b + a)
    return result
