from algopy import Txn, arc4, compile_logicsig, logicsig, op


@logicsig
def dont_use_this() -> bool:
    assert op.arg(1) == b"this is not secure", "arg is not correct"
    assert op.arg(0) == b"0"
    assert op.arg(2) == b"2"
    assert op.arg(3) == b"3"
    assert op.arg(4) == b"4"
    assert op.arg(Txn.num_app_args) == b"cant_happen"
    return True


class CheckCompiledSig(arc4.ARC4Contract):
    @arc4.abimethod()
    def check_sig_with_logic_sig_only_op_compiles(self) -> None:
        assert (
            Txn.sender == compile_logicsig(dont_use_this).account
        ), "expected to be signed by logic sig"
