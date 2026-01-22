from algopy import BigUInt, Contract, subroutine


class DivIdentityFoldBigUInt(Contract):
    def approval_program(self) -> bool:
        assert self_div(BigUInt(5)) == 1
        assert self_div(BigUInt(0)) == 1
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def self_div(x: BigUInt) -> BigUInt:
    # `x // x` must not be folded to 1 — if x is 0, the AVM panics
    return x // x
