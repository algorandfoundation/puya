from abc import ABC

from puyapy import Contract, Transaction, UInt64, arc4, subroutine


class MyBase(Contract, ABC):
    @subroutine
    def remember_creator(self) -> None:
        self.creator = Transaction.sender()


class MyMiddleBase(MyBase):
    @subroutine
    def calculate(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        return arc4.UInt64(a.decode() + b.decode())


@subroutine
def multiplicative_identity() -> UInt64:
    return UInt64(1)
