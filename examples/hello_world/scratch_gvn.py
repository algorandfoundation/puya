from algopy import Contract, UInt64, log, subroutine


class ScratchGVN(Contract):
    def approval_program(self) -> bool:
        n = UInt64(42)
        scratch_gvn_demo(n)
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def scratch_gvn_demo(n: UInt64) -> UInt64:
    a = n
    b = n
    while True:
        if not n:
            a = n
            b = n
        log(a)
        log(b)
        b = a
        a = b
        if not n:
            break
    return a + b
