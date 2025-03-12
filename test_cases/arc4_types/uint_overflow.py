from algopy import Txn, arc4


class UIntOverflow(arc4.ARC4Contract):
    @arc4.abimethod()
    def test_uint8(self) -> None:
        too_big = arc4.UInt8(Txn.num_app_args + 2**8)  # should fail here with overflow
        assert too_big.bytes != b"\x01", "this should not happen"

    @arc4.abimethod()
    def test_uint16(self) -> None:
        too_big = arc4.UInt16(Txn.num_app_args + 2**16)  # should fail here with overflow
        assert too_big.bytes != b"\x00\x01", "this should not happen"

    @arc4.abimethod()
    def test_uint32(self) -> None:
        too_big = arc4.UInt32(Txn.num_app_args + 2**32)  # should fail here with overflow
        assert too_big.bytes != b"\x00\x00\x00\x01", "this should not happen"
