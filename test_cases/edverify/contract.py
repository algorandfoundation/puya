from puyapy import Contract, UInt64, log, op


class VerifyContract(Contract):
    def approval_program(self) -> bool:
        assert op.Transaction.num_app_args == 3
        result = op.ed25519verify_bare(
            op.Transaction.application_args(0),
            op.Transaction.application_args(1),
            op.Transaction.application_args(2),
        )
        log(op.itob(UInt64(1) if result else UInt64(0)))
        return True

    def clear_state_program(self) -> bool:
        return True
