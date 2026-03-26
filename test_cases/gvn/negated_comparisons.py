from algopy import BigUInt, Contract, Txn, UInt64, subroutine


class NegatedComparisonContract(Contract):
    """Test contract for GVN negation-aware comparison numbering.

    Verifies that !(a >= b) is recognised as equivalent to (a < b),
    and likewise for all other inverse comparison pairs.
    """

    def approval_program(self) -> bool:
        a = Txn.num_app_args
        b = a + 1  # a < b always holds
        test_uint64_negated(a, b)
        test_biguint_negated(BigUInt(a), BigUInt(b))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_uint64_negated(a: UInt64, b: UInt64) -> None:
    """Each pair tests that !(inverse) gets the same VN as the direct comparison.

    All assertions hold when a < b.  GVN should recognise the negated
    assertion of each pair as redundant.
    """
    assert a < b
    assert not (a >= b)  # inverse of <

    assert a <= b
    assert not (a > b)  # inverse of <=

    assert a != b
    eq_result = a == b
    assert not eq_result  # !(==) should get same VN as !=


@subroutine(inline=False)
def test_biguint_negated(a: BigUInt, b: BigUInt) -> None:
    """Same as test_uint64_negated but for bytes comparisons (b<, b>, b<=, b>=, b==, b!=)."""
    assert a < b
    assert not (a >= b)  # inverse of b<

    assert a <= b
    assert not (a > b)  # inverse of b<=

    assert a != b
    eq_result = a == b
    assert not eq_result  # !(b==) should get same VN as b!=
