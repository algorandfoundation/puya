from algopy import Contract, ed25519verify_bare, Transaction, itob, log, UInt64


class VerifyContract(Contract):
    def approval_program(self) -> bool:
        assert Transaction.num_app_args() == 3
        result = ed25519verify_bare(
            Transaction.application_args(0),
            Transaction.application_args(1),
            Transaction.application_args(2),
        )
        log(itob(UInt64(1) if result else UInt64(0)))
        return True

    def clear_state_program(self) -> bool:
        return True
