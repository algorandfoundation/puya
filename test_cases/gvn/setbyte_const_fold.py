from algopy import Bytes, Contract, UInt64, op, subroutine


class SetByteConstFoldContract(Contract):
    """Test contract for GVN const-folding of the setbyte op.

    Verifies that setbyte(<const bytes>, <const uint64>, <const uint64>)
    collapses to a bytes constant in both intrinsic_simplifier (direct
    const path) and GVN (const visible only through a phi).
    """

    def approval_program(self) -> bool:
        test_direct()
        test_through_phi(UInt64(0))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_direct() -> None:
    # const args — collapses in intrinsic_simplifier
    assert op.setbyte(Bytes(b"AB"), 0, 90) == Bytes(b"ZB")  # 90 == ord('Z')
    assert op.setbyte(Bytes(b"AB"), 1, 90) == Bytes(b"AZ")


@subroutine(inline=False)
def test_through_phi(selector: UInt64) -> None:
    if selector:
        a = Bytes(b"A")
    else:
        a = Bytes(b"A")
    if selector:
        b = a + b"B"
    else:
        b = a + b"B"
    assert op.setbyte(b, 0, 67) == b"CB"  # 67 == ord('C')
