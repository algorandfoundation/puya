from algopy import ARC4Contract, arc4, op


class Contract(ARC4Contract, avm_version=12):
    @arc4.abimethod
    def test_new_ops(self) -> None:
        # op functions
        assert not op.falcon_verify(b"", b"", op.bzero(1793))
