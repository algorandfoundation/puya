from puyapy import Bytes, Contract, op, subroutine


class MyContract(Contract):
    def approval_program(self) -> bool:
        a = op.Transaction.application_args(0)
        b = op.Transaction.application_args(1)
        c = op.Transaction.application_args(2)
        d = op.Transaction.application_args(3)

        assert (a != c) or (b != d)
        assert four_args(a, b, c, d)
        two_args(a, b)
        two_args(c, d)

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def four_args(a: Bytes, b: Bytes, c: Bytes, d: Bytes) -> bool:
    return (a + b + c + d).length > 0


@subroutine
def two_args(a: Bytes, b: Bytes) -> None:
    assert a + b
