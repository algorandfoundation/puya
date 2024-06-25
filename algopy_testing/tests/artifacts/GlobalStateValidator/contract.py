from algopy import ARC4Contract, Txn, arc4, gtxn, op


class GlobalStateValidator(ARC4Contract):
    @arc4.abimethod
    def validate_g_args(self, arg1: arc4.UInt64, arg2: arc4.String) -> None:
        assert Txn.application_args(0) == arc4.arc4_signature("validate_g_args(uint64,string)void")
        assert Txn.application_args(1) == arg1.bytes
        assert Txn.application_args(2) == arg2.bytes
        assert gtxn.ApplicationCallTransaction(Txn.group_index).app_args(1) == arg1.bytes
        assert gtxn.Transaction(Txn.group_index).app_args(1) == arg1.bytes
        assert op.GTxn.application_args(Txn.group_index, 1) == arg1.bytes  # type: ignore[call-arg]
        assert op.Txn.application_args(1) == arg1.bytes
