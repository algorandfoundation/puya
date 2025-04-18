# ruff: noqa
from algopy import *


@subroutine
def unary_str() -> None:
    assert not ""
    assert not (not "abc")


@subroutine
def compare_str() -> None:
    assert not ("a" == "b")  # type: ignore[comparison-overlap]
    assert "a" != "b"  # type: ignore[comparison-overlap]
    assert "a" < "b"
    assert "a" <= "b"
    assert not ("a" > "b")
    assert not ("a" >= "b")
    assert "a" not in "b"
    assert not ("a" in "b")
    assert "a" in "abc"

    b = String("b")
    assert not ("a" == b)
    assert "a" != b
    assert "a" not in b
    assert not ("a" in b)
    assert "a" in String("abc")


@subroutine
def binary_op_str() -> None:
    assert "a" and "b"
    assert "a" or "b"
    assert "" or "b"
    assert not ("a" and "")
    assert not ("" or "")
    assert ("a" + "") == "a"


@subroutine
def unary_bytes() -> None:
    assert not b""
    assert not (not b"abc")


@subroutine
def unary_int() -> None:
    assert not 0
    assert not (not 1)
    assert -1 == (0 - 1)
    assert +1 == (0 + 1)
    assert ~0 == -1


@subroutine
def compare_int() -> None:
    assert not (0 == 1)  # type: ignore[comparison-overlap]
    assert 0 != 1  # type: ignore[comparison-overlap]
    assert 0 < 1
    assert 0 <= 1
    assert not (0 > 1)
    assert not (0 >= 1)

    one = UInt64(1)
    assert not (0 == one)
    assert 0 != one
    assert 0 < one
    assert 0 <= one
    assert not (0 > one)
    assert not (0 >= one)


@subroutine
def unary_bool() -> None:
    assert not False
    assert not (not True)
    assert -True == -1
    assert +False == 0
    assert ~True == -2


@subroutine
def tuples() -> None:
    assert (97, UInt64(98), 99) == tuple(b"abc")  # type: ignore[comparison-overlap]
    assert ("a", "b", "c") == tuple("abc")
    assert (97, UInt64(98), 99) == tuple(
        arc4.StaticArray(arc4.UInt64(97), arc4.UInt64(98), arc4.UInt64(99))
    )  # type: ignore[comparison-overlap]
    assert (1, 2) == tuple((1, 2))


class LiteralFolding(Contract):
    def approval_program(self) -> bool:
        unary_str()
        compare_str()
        binary_op_str()
        unary_bytes()
        unary_int()
        compare_int()
        unary_bool()
        tuples()
        return True

    def clear_state_program(self) -> bool:
        return True
