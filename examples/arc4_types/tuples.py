import typing

from puyapy import Bytes, Contract, UInt64, subroutine
from puyapy.arc4 import Bool, String, Tuple, UInt8

TestTuple: typing.TypeAlias = Tuple[UInt8, UInt8, String, String, UInt8]

TestBooleanPacking: typing.TypeAlias = Tuple[
    UInt8, Bool, Bool, Bool, Bool, Bool, Bool, Bool, Bool, Bool, UInt8
]


class Arc4TuplesTypeContract(Contract):
    def approval_program(self) -> bool:
        my_tuple = Tuple((UInt8(1), UInt8(2), String("hello"), String("world"), UInt8(255)))

        assert my_tuple == TestTuple.from_bytes(  # type: ignore[comparison-overlap]
            Bytes.from_hex("01020007000EFF000568656C6C6F0005776F726C64")
        )
        boolean_packing = Tuple(
            (
                UInt8(4),
                Bool(True),
                Bool(False),
                Bool(True),
                Bool(True),
                Bool(True),
                Bool(True),
                Bool(False),
                Bool(True),
                Bool(True),
                UInt8(16),
            )
        )
        assert boolean_packing.bytes == Bytes.from_hex("04BD8010")
        (a, b, c, d, e, f, g, h, i, j, k) = boolean_packing.decode()
        assert boolean_packing[10] == k
        assert a.decode() == 4, "a is 4"
        assert b and d and e and f and g and i and j, "b,d,e,f,g,i,j are true"
        assert not (c or h), "c and h are false"
        assert k.decode() == 16, "k is 16"

        assert boolean_packing == TestBooleanPacking.encode(boolean_packing.decode())

        total, concat = self.test_stuff(my_tuple)
        assert concat.decode() == b"hello world"
        assert total == 258

        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def test_stuff(self, test_tuple: TestTuple) -> tuple[UInt64, String]:
        a, b, c, d, e = test_tuple.decode()

        total = a.decode() + b.decode() + e.decode()
        text = c.decode() + b" " + d.decode()

        return total, String.encode(text)
