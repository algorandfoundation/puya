from algopy import Application, BigUInt, Bytes, Contract, String, UInt64, arc4, subroutine


class MyContract(Contract):
    """My contract"""

    def approval_program(self) -> UInt64:
        not_ten = UInt64(15)

        one_true = self.is_in_tuple_1(UInt64(10), (UInt64(10), not_ten, Bytes(b"five")))
        one_false = self.is_in_tuple_1(UInt64(5), (UInt64(10), not_ten, Bytes(b"five")))
        assert one_true, "Should be true"
        assert not one_false, "Should be false"

        two_true = self.is_in_tuple_2(
            Bytes(b"hello"), (Bytes(b"hello"), UInt64(0), Bytes(b"bonjour"))
        )
        two_false = self.is_in_tuple_2(
            Bytes(b"ciao"), (Bytes(b"hello"), UInt64(0), Bytes(b"bonjour"))
        )
        assert two_true, "Should be true"
        assert not two_false, "Should be false"

        three_true = self.is_in_tuple_3(
            BigUInt(32323423423423), (BigUInt(32323423423423), BigUInt(8439439483934))
        )
        three_false = self.is_in_tuple_3(
            BigUInt(32323423423423) + BigUInt(32323423423423),
            (BigUInt(32323423423423), BigUInt(8439439483934)),
        )
        assert three_true, "Should be true"
        assert not three_false, "Should be false"

        self.test_string_types()
        self.test_numeric_types()

        return UInt64(1)

    def clear_state_program(self) -> UInt64:
        return UInt64(1)

    @subroutine
    def is_in_tuple_1(self, x: UInt64, y: tuple[UInt64, UInt64, Bytes]) -> bool:
        return x in y

    @subroutine
    def is_in_tuple_2(self, x: Bytes, y: tuple[Bytes, UInt64, Bytes]) -> bool:
        return x in y

    @subroutine
    def is_in_tuple_3(self, x: BigUInt, y: tuple[BigUInt, BigUInt]) -> bool:
        return x in y

    @subroutine
    def test_string_types(self) -> None:
        assert foo_string() in (foo_string(), baz_string()), "foo in (foo, baz)"
        assert foo_string() not in (bar_string(), baz_string()), "foo not in (bar, baz)"
        assert foo_string() in (foo_arc4(), baz_string(), bar_string()), "foo in (foo, baz, bar)"
        assert foo_arc4() in (foo_string(), baz_string(), bar_string()), "foo in (foo, baz, bar)"
        assert foo_string() not in (bar_arc4(), baz_string()), "foo not in (bar, baz)"
        assert foo_arc4() not in (bar_arc4(), baz_string()), "foo not in (bar, baz)"
        assert foo_string() in (
            bar_arc4(),
            baz_string(),
            foo_string(),
            one_u64(),
        ), "foo in (bar, baz, foo, 1)"
        assert foo_arc4() in (
            bar_arc4(),
            baz_string(),
            foo_string(),
            one_u64(),
        ), "foo in (bar, baz, foo, 1)"
        assert foo_string() not in (
            bar_arc4(),
            baz_string(),
            one_u64(),
        ), "foo not in (bar, baz, 1)"
        assert foo_arc4() not in (bar_arc4(), baz_string(), one_u64()), "foo not in (bar, baz, 1)"
        assert Bytes(b"foo") not in (
            foo_string(),
            foo_arc4(),
            Bytes(b"bar"),
        ), "b'foo' not in (foo, foo, b'bar')"

    @subroutine
    def test_numeric_types(self) -> None:
        assert one_u64() in (one_u64(), two_u64()), "1 in (1, 2)"
        assert one_u64() not in (UInt64(3), two_u64()), "1 not in (3, 2)"

        assert one_u64() in (one_u64(), UInt64(3), two_u8()), "1 in (1, 3, 2)"
        assert one_u64() in (one_arc4u64(), UInt64(4), two_u8()), "1 in (1, 4, 2)"
        assert UInt64(2) in (one_arc4u64(), UInt64(3), two_u8()), "2 in (1, 3, 2)"
        assert two_u8() in (one_arc4u64(), UInt64(3), two_u8()), "2 in (1, 3, 2)"
        assert two_u8() in (one_arc4u64(), UInt64(2), UInt64(3)), "2 in (1, 2, 3)"
        assert three_u512() in (UInt64(3), UInt64(4)), "3 in (3, 4)"
        assert four_biguint() in (UInt64(5), UInt64(4)), "4 in (5, 4)"

        assert one_u64() not in (UInt64(5), two_u8()), "1 not in (5, 2)"
        assert one_u64() not in (Application(1), UInt64(3), two_u8()), "1 not in (app(1), 3, 2)"
        assert one_u64() not in (UInt64(3), two_u8()), "1 not in (3, 2)"
        assert UInt64(2) not in (one_arc4u64(), UInt64(3)), "2 not in (1, 3)"
        assert two_u8() not in (one_arc4u64(), UInt64(3)), "2 not in (1, 3)"
        assert two_u8() not in (one_arc4u64(), UInt64(3)), "2 not in (1, 3)"
        assert three_u512() not in (UInt64(5), UInt64(7)), "3 not in (5, 7)"
        assert four_biguint() not in (UInt64(2), UInt64(9)), "4 not in (2, 9)"

        assert one_u64() in (
            foo_string(),
            one_u64(),
            UInt64(3),
            two_u8(),
        ), "1 in (foo, 1, 3, 2)"
        assert one_u64() in (one_arc4u64(), bar_string(), two_u8()), "1 in (1, bar, 2)"
        assert UInt64(2) in (foo_arc4(), UInt64(3), two_u8()), "2 in (foo, 3, 2)"
        assert two_u8() in (bar_arc4(), UInt64(3), two_u8()), "2 in (bar, 3, 2)"
        assert two_u8() in (foo_string(), UInt64(2), UInt64(3)), "2 in foo(2, 3)"
        assert three_u512() in (UInt64(5), UInt64(3), foo_string()), "3 in (5, 3, foo)"

        assert one_u64() not in (
            foo_string(),
            UInt64(3),
            two_u8(),
        ), "1 not in (foo, 3, 2)"
        assert one_u64() not in (bar_string(), two_u8()), "1 not in (bar, 2)"
        assert UInt64(2) not in (foo_arc4(), UInt64(3)), "2 not in (foo, 3)"
        assert two_u8() not in (bar_arc4(), UInt64(3)), "2 not in (bar, 3)"
        assert two_u8() not in (foo_string(), UInt64(3)), "2 not in (foo, 3)"
        assert three_u512() not in (UInt64(5), foo_string()), "3 not in (5, foo)"
        assert arc4.UInt8(65) not in (
            Bytes(b"A"),
            UInt64(64),
            UInt64(66),
        ), "65 not in (b'A', 64, 66)"


@subroutine
def one_u64() -> UInt64:
    return UInt64(1)


@subroutine
def one_arc4u64() -> arc4.UInt64:
    return arc4.UInt64(1)


@subroutine
def two_u64() -> UInt64:
    return UInt64(2)


@subroutine
def two_u8() -> arc4.UInt8:
    return arc4.UInt8(2)


@subroutine
def three_u512() -> arc4.UInt512:
    return arc4.UInt512(3)


@subroutine
def four_biguint() -> BigUInt:
    return BigUInt(4)


@subroutine
def foo_string() -> String:
    return String("foo")


@subroutine
def foo_arc4() -> arc4.String:
    return arc4.String("foo")


@subroutine
def bar_string() -> String:
    return String("bar")


@subroutine
def bar_arc4() -> arc4.String:
    return arc4.String("bar")


@subroutine
def baz_string() -> String:
    return String("baz")
