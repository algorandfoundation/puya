import typing

from algopy import Txn, UInt64, arc4, itxn


class Hmmm(typing.NamedTuple):
    foo: UInt64
    bar: itxn.PaymentInnerTransaction


class ItxnNamedTuple(arc4.ARC4Contract):
    @arc4.abimethod()
    def named_tuple_itxn(self, amt: UInt64) -> None:
        hmm = Hmmm(foo=amt, bar=itxn.Payment(receiver=Txn.sender, amount=amt).submit())
        assert hmm.bar.amount == 0

    @arc4.abimethod()
    def named_tuple_itxn2(self, amt: UInt64) -> None:
        txn = Hmmm(foo=amt, bar=itxn.Payment(receiver=Txn.sender, amount=amt).submit()).bar
        assert txn.amount == 0

    @arc4.abimethod()
    def named_tuple_itxn3(self, amt: UInt64) -> None:
        hmmm = Hmmm(foo=amt, bar=itxn.Payment(receiver=Txn.sender, amount=amt).submit())
        txn = hmmm.bar
        assert txn.amount == 0
