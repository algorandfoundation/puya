from algopy import BigUInt, Bytes, Contract, UInt64, op, subroutine


class GVNConstFolding(Contract):
    """GVN const-folds (or identity-folds) intrinsic ops whose operands it proves
    constant. Several tests deliberately obscure the constant — identical phi branches,
    bzero/slice/btoi construction — so earlier passes can't fold it first; that
    scaffolding is load-bearing, not redundant.
    """

    def approval_program(self) -> bool:
        test_setbyte(True)
        test_uint64_mod(UInt64(42), False)
        test_biguint_mod(BigUInt(42**64), True)
        test_getbyte_direct()
        test_getbyte_through_phi(UInt64(0))
        test_replace3_large_index()
        test_replace3_through_phi(UInt64(0))
        test_addw()
        test_mulw()
        test_expw()
        test_divw()
        test_divmodw()
        test_btoi_itob_through_phi(UInt64(7))
        test_btoi_itob_through_phi(UInt64(0))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=False)
def test_setbyte(selector: bool) -> None:
    assert op.setbyte(b"AB", 0, 90) == b"ZB"
    assert op.setbyte(b"AB", 1, 90) == b"AZ"
    if selector:
        ab = op.bzero(100) + Bytes(b"AB")
    else:
        ab = op.bzero(100) + Bytes(b"AB")
    assert op.setbyte(ab, 100, 67) == op.bzero(100) + b"CB"


@subroutine(inline=False)
def test_uint64_mod(x: UInt64, selector: bool) -> None:
    assert x % 1 == 0
    if selector:
        one = op.btoi((op.bzero(65) + b"\x01")[-7:])
    else:
        one = op.btoi((op.bzero(66) + b"\x01")[-7:])
    assert x % one == 0


@subroutine(inline=False)
def test_biguint_mod(x: BigUInt, selector: bool) -> None:
    assert x % 1 == 0
    if selector:
        one = (op.bzero(65) + b"\x01")[-10:]
    else:
        one = (op.bzero(66) + b"\x01")[-10:]
    assert x % BigUInt.from_bytes(one) == 0


@subroutine(inline=False)
def test_getbyte_direct() -> None:
    assert op.getbyte(Bytes(b"hello"), 0) == 104
    assert op.getbyte(Bytes(b"hello"), 4) == 111


@subroutine(inline=False)
def test_getbyte_through_phi(selector: UInt64) -> None:
    if selector:
        b = Bytes(b"AB")
    else:
        b = Bytes(b"AB")
    assert op.getbyte(b, 1) == 66


@subroutine(inline=False)
def test_replace3_large_index() -> None:
    # index 256 > 255 so stack-to-immediate bails, leaving a replace3 for GVN to fold
    src = op.bzero(300)
    patched = op.replace(src, 256, Bytes(b"XYZ"))
    assert op.getbyte(patched, 256) == 88  # ord('X')


@subroutine(inline=False)
def test_replace3_through_phi(selector: UInt64) -> None:
    if selector:
        repl = Bytes(b"AB")
    else:
        repl = Bytes(b"AB")
    out = op.replace(Bytes(b"0000"), 1, repl)
    assert op.getbyte(out, 1) == 65


@subroutine(inline=False)
def test_addw() -> None:
    carry, lo = op.addw(2**63, 2**63)
    assert carry == 1
    assert lo == 0


@subroutine(inline=False)
def test_mulw() -> None:
    hi, lo = op.mulw(2**32, 2**32)
    assert hi == 1
    assert lo == 0


@subroutine(inline=False)
def test_expw() -> None:
    hi, lo = op.expw(2, 80)
    assert hi == 1 << 16
    assert lo == 0


@subroutine(inline=False)
def test_divw() -> None:
    q = op.divw(1, 0, 2)
    assert q == 1 << 63


@subroutine(inline=False)
def test_divmodw() -> None:
    qh, ql, rh, rl = op.divmodw(1, 2, 0, 3)
    assert qh == 0
    assert ql == ((1 << 64) + 2) // 3
    assert rh == 0
    assert rl == ((1 << 64) + 2) % 3


@subroutine(inline=False)
def test_btoi_itob_through_phi(x: UInt64) -> None:
    if x:
        b = op.itob(x)
    else:
        b = op.itob(x)
    assert op.btoi(b) == x
