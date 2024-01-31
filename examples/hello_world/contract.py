from puyapy import Contract, Transaction, log


class HelloWorldContract(Contract):
    def approval_program(self) -> bool:
        name = Transaction.application_args(0)
        log(b"Hello, " + name)
        return True

    def clear_state_program(self) -> bool:
        return True
