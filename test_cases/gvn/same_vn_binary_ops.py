from algopy import BigUInt, Contract, UInt64, subroutine


class SameVNBinaryOpsContract(Contract):
    """GVN folds binary ops whose two operands share a value number.

    - sub_bytes(v, v) -> b"" (biguint 0)
    - (v & v) -> v and (v | v) -> v

    intrinsic_simplifier has no self-operand rule, so these collapses are
    GVN-only.
    """

    def approval_program(self) -> bool:
        test_self_sub(BigUInt(42))
        test_self_bitwise(UInt64(42))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_self_sub(x: BigUInt) -> None:
    # both operands are x -> same value number -> sub_bytes folds to b"" (0n)
    assert x - x == 0


@subroutine(inline=False)
def test_self_bitwise(y: UInt64) -> None:
    # both operands share a value number -> bitwise and/or fold to the operand
    assert (y & y) == y
    assert (y | y) == y
