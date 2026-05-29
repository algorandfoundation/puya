from algopy import BigUInt, Contract, op, subroutine


class BigUIntOneConstVNContract(Contract):
    """GVN's biguint one-const algebra: x b* 1 -> x and 1 b* x -> x.

    The constant 1 is produced by two syntactically different expressions
    across a phi (differing bzero sizes), so intrinsic_simplifier cannot see
    the operand is constant; only GVN const-folds both arms to the same value
    number and applies the LEFT/RIGHT one-const simplifications.
    """

    def approval_program(self) -> bool:
        test_one_const(BigUInt(42), selector=True)
        test_one_const(BigUInt(42), selector=False)
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_one_const(x: BigUInt, *, selector: bool) -> None:
    if selector:
        one = BigUInt.from_bytes((op.bzero(65) + b"\x01")[-10:])
    else:
        one = BigUInt.from_bytes((op.bzero(66) + b"\x01")[-10:])
    # one == 1 (only GVN proves it). x b* 1 -> LEFT operand; 1 b* x -> RIGHT.
    assert x * one == x
    assert one * x == x
