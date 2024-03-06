from puyapy import Bytes, Contract, UInt64, log, subroutine


class BytesContract(Contract):
    def approval_program(self) -> UInt64:
        base_64 = Bytes.from_base64("QmFzZSA2NCBlbmNvZGVk")
        assert base_64 == Bytes(b"Base 64 encoded")
        base_32 = Bytes.from_base32("IJQXGZJAGMZCAZLOMNXWIZLE")
        assert base_32 == Bytes(b"Base 32 encoded")
        base_16 = Bytes.from_hex("4261736520313620656E636F646564")
        assert base_16 == Bytes(b"Base 16 encoded")

        empty = Bytes(b"")
        assert base_64, "Non empty bytes should be Truthy"
        assert not empty, "Empty bytes should be Falsy"

        assert Bytes(b"a") + Bytes(b"b") == Bytes(b"ab")

        c = Bytes(b"c")
        c += b"d"
        assert c == Bytes(b"cd")

        abc = Bytes(b"abc")
        assert abc[0] == b"a"

        assert abc[1:] == b"bc"
        assert abc[1:1] == b""
        assert abc[:1] == b"a"
        assert abc[:-1] == b"ab"
        assert abc[-2:] == b"bc"
        assert abc[-2:-1] == b"b"
        assert Bytes(b"1234567")[1:-1] == b"23456"
        assert abc[-10:10] == b"abc"

        true = Bytes(b"1")
        false = Bytes(b"")

        x = (true and true) == true
        assert x
        assert (true and true) == true
        assert (true and false) == false
        assert (false and true) == false
        assert (false and false) == false
        assert (true or true) == true
        assert (true or false) == true
        assert (false or true) == true
        assert (false or false) == false

        a, b, c, d = (
            Bytes.from_hex("00"),
            Bytes.from_hex("0F"),
            Bytes.from_hex("F0"),
            Bytes.from_hex("FF"),
        )

        assert a & b == a
        assert b | c == d
        assert b ^ d == c

        y = a
        y &= d
        assert y == a
        y |= d
        assert y == d
        y ^= c
        assert y == b

        check_slicing_with_uint64(abc)

        return UInt64(1)

    def clear_state_program(self) -> bool:
        return True


@subroutine
def check_slicing_with_uint64(abc: Bytes) -> None:
    one = UInt64(1)
    ten = UInt64(10)
    assert abc[one:] == b"bc"
    assert abc[one:one] == b""
    assert abc[:one] == b"a"
    assert one_to_seven()[one:-1] == b"23456"
    assert abc[UInt64(0) : ten] == b"abc"


@subroutine
def one_to_seven() -> Bytes:
    log("one_to_seven called")
    return Bytes(b"1234567")
