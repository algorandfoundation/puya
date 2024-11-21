from algopy import ARC4Contract, BigUInt, Bytes, arc4, subroutine


class Contract(ARC4Contract):
    @arc4.abimethod()
    def bytes_to_bool(self) -> bool:
        return bool(Bytes())

    @arc4.abimethod()
    def test_bytes_to_biguint(self) -> None:
        assert bytes_to_biguint()


@subroutine
def bytes_to_biguint() -> BigUInt:
    return BigUInt.from_bytes(Bytes())
