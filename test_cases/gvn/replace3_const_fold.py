from algopy import Bytes, Contract, UInt64, op, subroutine


class Replace3ConstFoldContract(Contract):
    """Test contract for GVN const-folding of the replace3 op.

    Verifies that replace3(<const bytes>, <const uint64>, <const bytes>)
    collapses to a bytes constant in both intrinsic_simplifier (direct
    const path) and GVN (const visible only through a phi). replace3 with
    start <= 255 is converted to replace2 by stack-to-immediate, so this
    test focuses on the cases where that conversion doesn't fire.
    """

    def approval_program(self) -> bool:
        test_large_index()
        test_through_phi(UInt64(0))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_large_index() -> None:
    # 300-byte source so we can replace at index 256 — stack-to-immediate
    # bails on indices > 255, so this must be folded as replace3.
    src = op.bzero(300)
    patched = op.replace(src, 256, Bytes(b"XYZ"))
    assert op.getbyte(patched, 256) == 88  # ord('X')


@subroutine(inline=False)
def test_through_phi(selector: UInt64) -> None:
    # const replacement arrives via a phi so intrinsic_simplifier can't see it,
    # but GVN can.
    if selector:
        repl = Bytes(b"AB")
    else:
        repl = Bytes(b"AB")
    out = op.replace(Bytes(b"0000"), 1, repl)
    assert op.getbyte(out, 1) == 65  # ord('A')
