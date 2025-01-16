from algopy import ARC4Contract, UInt64, arc4, logicsig, op


@logicsig(avm_version=12)
def avm_12_sig() -> UInt64:
    return op.sumhash512(b"").length


class Contract(ARC4Contract, avm_version=12):
    @arc4.abimethod
    def test_new_ops(self) -> None:
        # op functions
        assert not op.falcon_verify(b"", b"", op.bzero(1793))
        assert op.sumhash512(b"")
