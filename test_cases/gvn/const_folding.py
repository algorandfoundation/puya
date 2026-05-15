from algopy import ARC4Contract, Bytes, op, public, subroutine


class GVNConstFolding(ARC4Contract):
    @public
    def entry(self) -> None:
        test_setbyte(True)


@subroutine(inline=False)
def test_setbyte(selector: bool) -> None:
    # const args — collapses in intrinsic_simplifier
    assert op.setbyte(b"AB", 0, 90) == b"ZB"  # 90 == ord('Z')
    assert op.setbyte(b"AB", 1, 90) == b"AZ"

    if selector:
        a = Bytes(b"A")
    else:
        a = Bytes(b"A")
    if selector:
        b = a + b"B"
    else:
        b = a + b"B"
    assert op.setbyte(b, 0, 67) == b"CB"  # 67 == ord('C')
