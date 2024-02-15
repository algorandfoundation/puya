from puyapy import Contract, UInt64, log, subroutine


class MyContract(Contract):
    def approval_program(self) -> UInt64:
        log(42)
        self.echo(UInt64(1), UInt64(2))
        return UInt64(1)

    @subroutine
    def echo(self, a: UInt64, b: UInt64) -> None:
        log(a)
        log(b)

    def clear_state_program(self) -> UInt64:
        return UInt64(1)
