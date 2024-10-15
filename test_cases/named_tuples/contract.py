import typing

from algopy import BigUInt, Bytes, String, Txn, UInt64, arc4, subroutine


class TestTuple(typing.NamedTuple):
    """This is a test tuple"""

    a: UInt64
    b: BigUInt
    c: String
    d: Bytes


class NamedTuplesContract(arc4.ARC4Contract):

    @arc4.abimethod()
    def build_tuple(self, a: UInt64, b: BigUInt, c: String, d: Bytes) -> TestTuple:
        t1 = self.build_tuple_by_name(a, b, c, d)
        t2 = self.build_tuple_by_position(a, b, c, d)
        assert t1 == t2
        return t1

    @subroutine
    def build_tuple_by_name(self, a: UInt64, b: BigUInt, c: String, d: Bytes) -> TestTuple:
        return TestTuple(a=a, b=b, c=c, d=d)

    @subroutine
    def build_tuple_by_position(self, a: UInt64, b: BigUInt, c: String, d: Bytes) -> TestTuple:
        return TestTuple(a, b, c, d)

    @arc4.abimethod()
    def test_tuple(self, value: TestTuple) -> None:
        assert value.a < 1000
        assert value.b < 2**65
        assert value.c.bytes.length > 1
        assert value.d == Txn.sender.bytes
