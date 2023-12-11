from puyapy import UInt64, BigUInt, subroutine, Contract, Transaction, btoi


class Baddie(Contract):
    def approval_program(self) -> bool:
        test_case = Transaction.application_args(0)
        invert_second_condition = (
            Transaction.num_app_args() > 1 and btoi(Transaction.application_args(1)) > 0
        )

        if invert_second_condition:
            if test_case == b"uint":
                assert test_uint_undefined(True, False) == 10
                assert test_uint_undefined(False, True) == 8  # 💥
            elif test_case == b"bytes":
                assert test_bytes_undefined(True, False) == 10
                assert test_bytes_undefined(False, True) == 8  # 💥
            else:
                assert test_mixed_undefined(True, False) == 10
                assert test_mixed_undefined(False, True) == 8  # 💥
        else:
            if test_case == b"uint":
                assert test_uint_undefined(True, True) == 8
                assert test_uint_undefined(False, False) == 10
            elif test_case == b"bytes":
                assert test_bytes_undefined(True, True) == 8
                assert test_bytes_undefined(False, False) == 10
            else:
                assert test_mixed_undefined(True, True) == 8
                assert test_mixed_undefined(False, False) == 10
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def test_uint_undefined(x: bool, y: bool) -> UInt64:
    if x:
        a = UInt64(7)
    if x:
        b = UInt64(11)
    else:
        b = UInt64(11)
    if y:
        c = (
            a
            # 💥
            + 1
        )
    else:
        c = b - 1
    return c


@subroutine
def test_bytes_undefined(x: bool, y: bool) -> BigUInt:
    if x:
        a = BigUInt(7)
    if x:
        b = BigUInt(11)
    else:
        b = BigUInt(11)
    if y:
        c = (
            a
            # 💥
            + 1
        )
    else:
        c = b - 1
    return c


@subroutine
def test_mixed_undefined(x: bool, y: bool) -> BigUInt:
    if x:
        a = UInt64(7)
    if x:
        b = BigUInt(11)
    else:
        b = BigUInt(11)
    if y:
        c = BigUInt(
            # 💥
            a
        ) + BigUInt(1)
    else:
        c = b - 1
    return c
