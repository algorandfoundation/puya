from abc import ABC

from algopy import Contract, Transaction, UInt64, subroutine


class MyBase(Contract, ABC):
    @subroutine
    def remember_creator(self) -> None:
        self.creator = Transaction.sender()


class MyMiddleBase(MyBase):
    @subroutine
    def calculate(self, a: UInt64, b: UInt64) -> UInt64:
        return a + b


@subroutine
def multiplicative_identity() -> UInt64:
    return UInt64(1)
