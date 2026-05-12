from algopy import Contract, UInt64, op, subroutine


class WideMathConstFoldContract(Contract):
    """Test contract for GVN const-folding of wide-math AVM ops.

    Verifies that addw / mulw / expw / divw / divmodw with constant inputs
    collapse to constant tuples (or a single constant for divw) end-to-end.
    """

    def approval_program(self) -> bool:
        test_addw()
        test_mulw()
        test_expw()
        test_divw()
        test_divmodw()
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_addw() -> None:
    carry, lo = op.addw(UInt64(2**63), 2**63)
    assert carry == 1
    assert lo == 0


@subroutine(inline=False)
def test_mulw() -> None:
    hi, lo = op.mulw(UInt64(2**32), 2**32)
    assert hi == 1
    assert lo == 0


@subroutine(inline=False)
def test_expw() -> None:
    hi, lo = op.expw(UInt64(2), 80)
    # 2^80 = 0x10_0000_0000_0000_0000_0000 — hi has the high 16 bits set.
    assert hi == 1 << 16
    assert lo == 0


@subroutine(inline=False)
def test_divw() -> None:
    q = op.divw(UInt64(1), 0, 2)  # (2^64) / 2 = 2^63
    assert q == 1 << 63


@subroutine(inline=False)
def test_divmodw() -> None:
    qh, ql, rh, rl = op.divmodw(UInt64(1), 2, 0, 3)
    # dividend = 2^64 + 2, divisor = 3
    # quotient = (2^64 + 2) // 3, remainder = (2^64 + 2) % 3
    assert qh == 0
    assert ql == ((1 << 64) + 2) // 3
    assert rh == 0
    assert rl == ((1 << 64) + 2) % 3
