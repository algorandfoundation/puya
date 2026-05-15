from algopy import ARC4Contract, BigUInt, Bytes, UInt64, op, public, subroutine


class GVNConstFolding(ARC4Contract):
    @public
    def entry(self) -> None:
        test_setbyte(True)
        test_uint64_mod(UInt64(42), False)
        test_biguint_mod(BigUInt(42**64), True)


@subroutine(inline=False)
def test_setbyte(selector: bool) -> None:
    # simple cases which collapse in intrinsic_simplifier
    assert op.setbyte(b"AB", 0, 90) == b"ZB"  # 90 == ord('Z')
    assert op.setbyte(b"AB", 1, 90) == b"AZ"

    # demonstrate GVN ability to handle larger constants
    # and also punch through Phi nodes
    if selector:
        ab = op.bzero(100) + Bytes(b"AB")
    else:
        ab = op.bzero(100) + Bytes(b"AB")
    assert op.setbyte(ab, 100, 67) == op.bzero(100) + b"CB"  # 67 == ord('C')


@subroutine(inline=False)
def test_uint64_mod(x: UInt64, selector: bool) -> None:
    # simple case — collapses in intrinsic_simplifier
    assert x % 1 == 0

    # demonstrate GVN ability to handle larger constants
    # and also punch through Phi nodes
    if selector:
        one = op.btoi((op.bzero(65) + b"\x01")[-10:])
    else:
        one = op.btoi((op.bzero(66) + b"\x01")[-10:])
    assert x % one == 0


@subroutine(inline=False)
def test_biguint_mod(x: BigUInt, selector: bool) -> None:
    # simple case — collapses in intrinsic_simplifier
    assert x % 1 == 0

    # demonstrate GVN ability to handle larger constants
    # and also punch through Phi nodes
    if selector:
        one = (op.bzero(65) + b"\x01")[-10:]
    else:
        one = (op.bzero(66) + b"\x01")[-10:]
    assert x % BigUInt.from_bytes(one) == 0
