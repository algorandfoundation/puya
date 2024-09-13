# ruff: noqa
from algopy import *


class BooleanBinaryOps(Contract):
    def approval_program(self) -> bool:
        test_boolean_binary_ops(true=True, false=False)
        test_boolean_shortcircuit_binary_ops()
        type_coercion()
        test_union_boolean_binary_ops()
        test_literal_boolean_binary_ops()
        test_literal_conditionals(true=True, false=False)
        return True

    def clear_state_program(self) -> bool:
        assert bool() == False
        return True


@subroutine
def test_boolean_binary_ops(*, true: bool, false: bool) -> None:
    assert not (true and false)
    assert not (false and true)
    assert true and true
    assert not (false and false)

    assert true or false
    assert false or true
    assert true or true
    assert not (false or false)


@subroutine
def bool_to_bytes(x: bool) -> Bytes:
    return Bytes(b"true" if x else b"false")


@subroutine
def test_boolean_shortcircuit_binary_ops() -> None:
    for lhs in (True, False):
        for rhs in (True, False):
            and_msg = b"_" + bool_to_bytes(lhs) + b"_and_" + bool_to_bytes(rhs)
            and_result = log_and_return(lhs, b"lhs" + and_msg) and log_and_return(
                rhs, b"rhs" + and_msg
            )
            assert and_result == (lhs and rhs)
            or_msg = b"_" + bool_to_bytes(lhs) + b"_or_" + bool_to_bytes(rhs)
            or_result = log_and_return(lhs, b"lhs" + or_msg) or log_and_return(
                rhs, b"rhs" + or_msg
            )
            assert or_result == (lhs or rhs)


@subroutine
def log_and_return(x: bool, msg: Bytes) -> bool:
    log(msg)
    return x


@subroutine
def type_coercion() -> None:
    b = UInt64(0) or OnCompleteAction.OptIn
    assert b > 0
    c = TransactionType.ApplicationCall or UInt64(0) or OnCompleteAction.OptIn
    assert c == TransactionType.ApplicationCall


@subroutine
def test_union_boolean_binary_ops() -> None:
    ok = bool(Bytes() or UInt64(1))
    assert ok

    x = UInt64(0)
    y = Bytes(b"y")
    z = String("z")
    assert (x or y) or (y or z)
    assert (x or y) and (x or y)
    assert x or (y or z)
    assert (x or y) or z

    assert (String("left") and String("right")).startswith("ri")
    assert String("right").startswith(String("le") and String("ri"))

    bytes_to_iterate = Bytes(b"abc")
    for idx, b in uenumerate(Bytes(b"never seen") and bytes_to_iterate):
        assert b == bytes_to_iterate[idx]
    assert (Bytes(b"left") and Bytes(b"right"))[1] == b"i"
    assert (Bytes(b"left") or Bytes(b"right"))[0:2] == b"le"
    assert "ight" in (String("left") and String("right"))

    assert (UInt64(1) and UInt64(2)) + 3 == 5
    assert ~(UInt64(1) or UInt64(2)) == ~UInt64(1)


@subroutine
def test_literal_boolean_binary_ops() -> None:
    assert 0 or 1
    assert "abc" and 1
    assert UInt64(0) or 1
    assert False or Bytes(b"abc")

    a = bool(0 or 1)
    b = bool("abc" and 1)
    c = bool(UInt64(0) or 1)
    d = bool(False or Bytes(b"abc"))
    assert a and b and c and d

    if 0 and 1:
        assert False
    if "abc" and 0:
        assert False
    if UInt64(0) or 0:
        assert False
    if False or Bytes(b""):
        assert False

    assert UInt64(1 and 2) == 2

    one = UInt64(1)
    assert op.bitlen(one and 4) == 3
    empty_bytes = Bytes()
    assert op.bitlen(empty_bytes or b"hello") > 0


@subroutine
def test_literal_conditionals(*, true: bool, false: bool) -> None:
    assert (3 if false else 0) or 4
    assert 0 or (3 if true else 0)
    assert b"123" or (3 if true else 0)
    assert (3 if false else 0) or b"123"
    y = UInt64((3 if false else 0) or 4)
    assert y == 4
    z = UInt64(0 or (3 if true else 0))
    assert z == 3
