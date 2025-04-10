import typing

from algopy import Account, Application, Asset, UInt64, arc4, size_of


class WhatsMySize(typing.NamedTuple):
    foo: UInt64
    bar: bool


class MyContract(arc4.ARC4Contract):
    @arc4.abimethod()
    def test(self) -> None:
        assert size_of(arc4.UInt64) == 8
        assert size_of(UInt64) == 8
        assert size_of(arc4.Address) == 32
        assert size_of(Account) == 32
        assert size_of(Application) == 8
        assert size_of(Asset) == 8
        assert size_of(bool) == 8
        assert size_of(tuple[bool]) == 1
        assert size_of(tuple[bool, bool, bool, bool, bool, bool, bool, bool]) == 1
        assert size_of(tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]) == 2
        assert size_of(WhatsMySize) == 9
        assert size_of(arc4.StaticArray[arc4.Byte, typing.Literal[7]]) == 7
        assert size_of(arc4.StaticArray(arc4.Byte(), arc4.Byte())) == 2
