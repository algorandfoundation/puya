# ruff: noqa: SIM201, SIM202, SIM300, PLR0124
import typing as t

from algopy import BigUInt, Contract, UInt64, arc4, subroutine


class UIntNOrdering(Contract):
    def approval_program(self) -> bool:
        check_both_uint_n(arc4.Byte(1), arc4.UInt64(2))
        check_mixed(arc4.Byte(1), arc4.BigUIntN[t.Literal[264]](2))
        check_both_big_uint_n(arc4.UInt256(1), arc4.BigUIntN[t.Literal[264]](2))
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def check_both_uint_n(one: arc4.Byte, two: arc4.UInt64) -> None:
    one_uint64 = UInt64(1)
    one_biguint = BigUInt(1)

    two_uint64 = UInt64(2)
    two_biguint = BigUInt(2)

    assert one == 1
    assert 1 == one
    assert one == one
    assert one == one_uint64
    assert one == one_biguint
    assert not (one == 2)
    assert not (one == two)
    assert not (one == two_uint64)
    assert not (one == two_biguint)

    assert not (one != 1)
    assert not (1 != one)
    assert not (one != one)
    assert not (one != one_uint64)
    assert not (one != one_biguint)
    assert one != 2
    assert one != two
    assert one != two_uint64
    assert one != two_biguint

    assert one <= 1
    assert 1 <= one
    assert one <= one
    assert one <= one_uint64
    assert one <= one_biguint
    assert one <= 2
    assert one <= two
    assert one <= two_uint64
    assert one <= two_biguint

    assert not (one < 1)
    assert not (1 < one)
    assert not (one < one)
    assert not (one < one_uint64)
    assert not (one < one_biguint)
    assert one < 2
    assert one < two
    assert one < two_uint64
    assert one < two_biguint

    assert one >= 1
    assert 1 >= one
    assert one >= one
    assert one >= one_uint64
    assert one >= one_biguint
    assert not (one >= 2)
    assert not (one >= two)
    assert not (one >= two_uint64)
    assert not (one >= two_biguint)

    assert not (one > 1)
    assert not (1 > one)
    assert not (one > one)
    assert not (one > one_uint64)
    assert not (one > one_biguint)
    assert not (one > 2)
    assert not (one > two)
    assert not (one > two_uint64)
    assert not (one > two_biguint)


@subroutine
def check_mixed(one: arc4.Byte, two: arc4.BigUIntN[t.Literal[264]]) -> None:
    one_uint64 = UInt64(1)
    one_biguint = BigUInt(1)

    two_uint64 = UInt64(2)
    two_biguint = BigUInt(2)

    assert one == 1
    assert 1 == one
    assert one == one
    assert one == one_uint64
    assert one == one_biguint
    assert not (one == 2)
    assert not (one == two)
    assert not (one == two_uint64)
    assert not (one == two_biguint)

    assert not (one != 1)
    assert not (1 != one)
    assert not (one != one)
    assert not (one != one_uint64)
    assert not (one != one_biguint)
    assert one != 2
    assert one != two
    assert one != two_uint64
    assert one != two_biguint

    assert one <= 1
    assert 1 <= one
    assert one <= one
    assert one <= one_uint64
    assert one <= one_biguint
    assert one <= 2
    assert one <= two
    assert one <= two_uint64
    assert one <= two_biguint

    assert not (one < 1)
    assert not (1 < one)
    assert not (one < one)
    assert not (one < one_uint64)
    assert not (one < one_biguint)
    assert one < 2
    assert one < two
    assert one < two_uint64
    assert one < two_biguint

    assert one >= 1
    assert 1 >= one
    assert one >= one
    assert one >= one_uint64
    assert one >= one_biguint
    assert not (one >= 2)
    assert not (one >= two)
    assert not (one >= two_uint64)
    assert not (one >= two_biguint)

    assert not (one > 1)
    assert not (1 > one)
    assert not (one > one)
    assert not (one > one_uint64)
    assert not (one > one_biguint)
    assert not (one > 2)
    assert not (one > two)
    assert not (one > two_uint64)
    assert not (one > two_biguint)


@subroutine
def check_both_big_uint_n(one: arc4.UInt256, two: arc4.BigUIntN[t.Literal[264]]) -> None:
    one_uint64 = UInt64(1)
    one_biguint = BigUInt(1)

    two_uint64 = UInt64(2)
    two_biguint = BigUInt(2)

    assert one == 1
    assert 1 == one
    assert one == one
    assert one == one_uint64
    assert one == one_biguint
    assert not (one == 2)
    assert not (one == two)
    assert not (one == two_uint64)
    assert not (one == two_biguint)

    assert not (one != 1)
    assert not (1 != one)
    assert not (one != one)
    assert not (one != one_uint64)
    assert not (one != one_biguint)
    assert one != 2
    assert one != two
    assert one != two_uint64
    assert one != two_biguint

    assert one <= 1
    assert 1 <= one
    assert one <= one
    assert one <= one_uint64
    assert one <= one_biguint
    assert one <= 2
    assert one <= two
    assert one <= two_uint64
    assert one <= two_biguint

    assert not (one < 1)
    assert not (1 < one)
    assert not (one < one)
    assert not (one < one_uint64)
    assert not (one < one_biguint)
    assert one < 2
    assert one < two
    assert one < two_uint64
    assert one < two_biguint

    assert one >= 1
    assert 1 >= one
    assert one >= one
    assert one >= one_uint64
    assert one >= one_biguint
    assert not (one >= 2)
    assert not (one >= two)
    assert not (one >= two_uint64)
    assert not (one >= two_biguint)

    assert not (one > 1)
    assert not (1 > one)
    assert not (one > one)
    assert not (one > one_uint64)
    assert not (one > one_biguint)
    assert not (one > 2)
    assert not (one > two)
    assert not (one > two_uint64)
    assert not (one > two_biguint)
