from algopy import ARC4Contract, UInt64, arc4, logicsig, op


@logicsig(avm_version=13)
def avm_13_sig() -> UInt64:
    return op.sumhash512(b"").length


class Contract(ARC4Contract, avm_version=13):
    @arc4.abimethod
    def test_new_ops(self) -> None:
        # op functions
        assert op.sumhash512(b"")
