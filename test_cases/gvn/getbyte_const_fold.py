from algopy import Bytes, Contract, UInt64, op, subroutine


class GetByteConstFoldContract(Contract):
    """Test contract for GVN const-folding of the getbyte op.

    Verifies that getbyte(<const bytes>, <const uint64>) collapses to a
    uint64 constant in both intrinsic_simplifier (direct const path)
    and GVN (const visible only through a phi).
    """

    def approval_program(self) -> bool:
        test_direct()
        test_through_phi(UInt64(0))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_direct() -> None:
    # const bytes + const index — collapses in intrinsic_simplifier
    assert op.getbyte(Bytes(b"hello"), 0) == 104  # 'h'
    assert op.getbyte(Bytes(b"hello"), 4) == 111  # 'o'


@subroutine(inline=False)
def test_through_phi(selector: UInt64) -> None:
    # selector flows through a phi but both arms produce the same const-foldable arg;
    # only GVN sees the equivalence and folds the getbyte.
    if selector:
        b = Bytes(b"AB")
    else:
        b = Bytes(b"AB")
    assert op.getbyte(b, 1) == 66  # 'B'
