from puyapy import Contract, UInt64, itob, log, subroutine, urange


class UnSSAContract(Contract):
    def approval_program(self) -> bool:
        test_self_ref_phi()
        result1 = test_swap(UInt64(1))
        log(itob(result1))
        assert 1 <= result1 <= 2
        result2 = test_swap(UInt64(2))
        log(itob(result2))
        assert 1 <= result2 <= 2
        test_swap_loop(UInt64(7), UInt64(11))
        assert test_param_update_with_reentrant_entry_block(UInt64(0)) == 10
        test_param_update_with_reentrant_entry_block_v2(UInt64(0))
        test_param_update_with_reentrant_entry_block_v3()
        test_swap_args()

        (a, b) = test_tuple_swap(UInt64(100), UInt64(200), UInt64(0))
        assert a == UInt64(100)
        assert b == UInt64(200)
        (a, b) = test_tuple_swap(UInt64(100), UInt64(200), UInt64(1))
        assert a == UInt64(200)
        assert b == UInt64(100)

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def test_self_ref_phi() -> UInt64:
    a = UInt64(1)
    while a < 100:
        if a % 105 == 0:
            continue
        if not a % 21:
            break
        a += 1
    return a


@subroutine
def test_swap(i: UInt64) -> UInt64:
    x = UInt64(1)
    y = UInt64(2)
    while i > 0:
        tmp = x
        x = y
        y = tmp
        i = i - 1
    return x


@subroutine
def test_swap_loop(i: UInt64, j: UInt64) -> UInt64:
    x = UInt64(1)
    y = UInt64(2)
    while i > 0:
        while j > 0:
            tmp = x
            x = y
            y = tmp
            j = j - 1
        i = i - 1
    return x


@subroutine
def test_tuple_swap(a: UInt64, b: UInt64, i: UInt64) -> tuple[UInt64, UInt64]:
    for _item in urange(i):
        (a, b) = (b, a)
    return a, b


@subroutine
def test_param_update_with_reentrant_entry_block(x: UInt64) -> UInt64:
    while True:
        x = x + 1
        if x >= 10:
            break
    return x


@subroutine
def test_param_update_with_reentrant_entry_block_v2(x: UInt64) -> UInt64:
    x = x + 1
    while True:
        if x >= 1:
            break
    return x


@subroutine
def test_param_update_with_reentrant_entry_block_v3() -> None:
    while True:
        if one():
            break


@subroutine
def one() -> UInt64:
    return UInt64(1)


@subroutine
def swap_args(a: UInt64, b: UInt64) -> tuple[UInt64, UInt64]:
    return b, a


@subroutine
def test_swap_args() -> None:
    a = one() + 123
    b = one() + 234
    a, b = swap_args(a, b)
    assert a == 235, "a == 235"
    assert b == 124, "b = 124"


# TODO: lost copy problem example/test
