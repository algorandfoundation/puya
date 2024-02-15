from puyapy import Contract, log, op


class HelloWorldContract(Contract):
    def approval_program(self) -> bool:
        name = op.Transaction.application_args(0)
        log(b"Hello, " + name)
        return True

    def clear_state_program(self) -> bool:
        return True
