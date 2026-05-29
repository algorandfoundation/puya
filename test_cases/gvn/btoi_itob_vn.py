from algopy import Contract, UInt64, op, subroutine


class BtoiItobVNContract(Contract):
    """Test contract for GVN's btoi(itob(x)) -> x value-numbering rule.

    For non-const x, itob(x) is not folded to a constant. By hiding the
    itob result behind a phi, only GVN (not intrinsic_simplifier) can see
    that btoi's argument was produced by itob, collapsing btoi(itob(x)) to x.
    """

    def approval_program(self) -> bool:
        test_through_phi(UInt64(7))
        test_through_phi(UInt64(0))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_through_phi(x: UInt64) -> None:
    if x:
        b = op.itob(x)
    else:
        b = op.itob(x)
    # both phi arms are itob(x) — GVN numbers them equal, collapses the phi,
    # then recognises btoi(<itob result>) and returns x's value number.
    assert op.btoi(b) == x
