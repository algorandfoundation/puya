from algopy import Contract, Txn


class MyContract(Contract):
    def approval_program(self) -> bool:
        a = Txn.application_args(0)
        b = Txn.application_args(1)

        assert a + b
        return (b + a).length > 0

    def clear_state_program(self) -> bool:
        return True
