from abc import ABC

from algopy import Contract, UInt64, arc4, op, subroutine


class MyBase(Contract, ABC):
    @subroutine
    def remember_creator(self) -> None:
        self.creator = op.Txn.sender


class MyMiddleBase(MyBase, ABC):
    @subroutine
    def calculate(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        return arc4.UInt64(a.as_uint64() + b.as_uint64())


@subroutine
def multiplicative_identity() -> UInt64:
    return UInt64(1)
