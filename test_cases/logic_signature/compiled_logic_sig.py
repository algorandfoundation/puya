from algopy import Txn, arc4, compile_logicsig, logicsig, op


@logicsig
def dont_use_this() -> bool:
    assert op.arg(1) == b"this is not secure", "arg is not correct"
    return True


class CheckCompiledSig(arc4.ARC4Contract):
    @arc4.abimethod()
    def check_sig_with_logic_sig_only_op_compiles(self) -> None:
        assert (
            Txn.sender == compile_logicsig(dont_use_this).account
        ), "expected to be signed by logic sig"
