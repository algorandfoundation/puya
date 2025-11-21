from algopy import BaseContract, UInt64, subroutine


class DivIdentityFoldUInt64(BaseContract):
    def approval_program(self) -> bool:
        assert self_div(UInt64(5)) == 1
        assert self_div(UInt64(0)) == 1
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def self_div(x: UInt64) -> UInt64:
    # `x // x` must not be folded to 1 — if x is 0, the AVM panics
    return x // x
