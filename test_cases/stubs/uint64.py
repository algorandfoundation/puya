from algopy import Contract, Txn, UInt64, op


class Uint64Contract(Contract):
    def approval_program(self) -> UInt64:
        zero = UInt64(0)
        one = UInt64(1)
        two = UInt64(2)
        five = UInt64(5)
        three = UInt64(3)
        sixty = UInt64(60)

        assert one, "Any non-zero number should be Truthy"
        assert not zero, "Zero should beFalsy"

        assert one < five
        assert five > one
        assert one <= one  # noqa: PLR0124
        assert five >= five  # noqa: PLR0124

        assert one + five == 6

        c = five
        c += sixty
        assert c == 65

        assert sixty - five == 55
        c -= five
        assert c == 60

        assert sixty // five == 12
        c //= five

        assert c == 12

        assert five * sixty == 300

        assert five**three == 125

        c **= 2

        assert c == 144

        assert one << two == 4
        c >>= 6
        assert c == 2
        c <<= 6
        assert c == 128
        assert five >> three == 0

        assert ~one == 0xFFFFFFFFFFFFFFFE

        true = UInt64(1)
        false = UInt64(0)
        assert (true and true) == true
        assert (true and false) == false
        assert (false and true) == false
        assert (false and false) == false
        assert (true or true) == true
        assert (true or false) == true
        assert (false or true) == true
        assert (false or false) == false

        assert one & five == one
        assert sixty | five == 61
        assert sixty ^ five == 57

        y = UInt64(0b11111110)
        y &= UInt64(0b00011111)
        assert y == 0b00011110
        y |= 0b00110110
        assert y == 0b00111110
        y ^= 0b11111111
        assert y == 0b11000001

        assert op.sqrt(UInt64(17)) == op.sqrt(16)

        assert one == +one

        assert UInt64(1 if Txn.num_app_args else 5) == 5, "constructor expressions supported"

        return UInt64(1)

    def clear_state_program(self) -> bool:
        assert UInt64() == 0
        assert UInt64(False) == 0
        return True
