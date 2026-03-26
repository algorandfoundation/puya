from algopy import BigUInt, Contract, Txn, UInt64, subroutine


class ComparisonSwapsContract(Contract):
    """Test contract for GVN ordering-op canonicalization.

    Verifies that a<b and b>a (and <=/>= variants, including bytes
    comparisons) are recognised as equivalent by GVN's swapped-predicate
    canonicalization.
    """

    def approval_program(self) -> bool:
        test_uint64_swaps(Txn.num_app_args, Txn.num_app_args + 1)
        test_biguint_swaps(BigUInt(1), BigUInt(2))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_uint64_swaps(a: UInt64, b: UInt64) -> None:
    """Each pair of asserts tests a swapped-predicate equivalence.

    GVN should recognise the second assert of each pair as redundant
    because a<b and b>a (and a<=b and b>=a) get the same canonical
    value number.
    """
    assert a < b
    assert b > a  # converse of a < b

    assert a <= b
    assert b >= a  # converse of a <= b


@subroutine(inline=False)
def test_biguint_swaps(a: BigUInt, b: BigUInt) -> None:
    """Same as test_uint64_swaps but for bytes comparisons (b<, b>, b<=, b>=)."""
    assert a < b
    assert b > a  # converse of a < b

    assert a <= b
    assert b >= a  # converse of a <= b
