from algopy import Bytes, Contract, UInt64, log, op, subroutine, urange


class TupleSupport(Contract):
    def __init__(self) -> None:
        self.state = UInt64(0)

    def approval_program(self) -> UInt64:
        total = add_three_values((UInt64(101), UInt64(102), UInt64(103)))
        log(total)
        (a, b) = (UInt64(1), UInt64(2))
        (did_overflow, self.state) = op.addw(a, b)
        assert not did_overflow, "overflow!"
        ab = (a, b)
        assert ab[-1] == ab[1]
        result = op.addw(a, b)
        assert not result[0], "overflow!"
        c = d = UInt64(3)
        (a2, b2) = ab
        cd = (c, d)
        ab2 = ab
        # ((a2, b2), cd, ab2) = (ab, (c, d), ab) # TODO: support this instead of 3 lines above
        if a == b:
            tup = ab2
        else:
            tup = cd
        assert a2 == a
        assert b2 == b
        assert cd[0] == tup[0]
        assert cd[1] == tup[1]

        # assert ab2 == ab # TODO: support ths
        # foobar = ((a, b), (c, d)) # TODO: negative test for this
        log(bytes_combine((Bytes(b"Hello, "), Bytes(b"world!"))))
        max_uint64 = UInt64(2**64 - 1)
        hi, mid, lo = addw2(op.addw(max_uint64, max_uint64), op.addw(a, b))
        log(hi)
        log(mid)
        log(lo)
        log(bytes_multiply((Bytes(b"na"), UInt64(5))))
        test_tuple_swap(zero=UInt64(0))
        slicing(
            (
                UInt64(1),
                UInt64(2),
                UInt64(3),
                UInt64(4),
                UInt64(5),
                UInt64(6),
                UInt64(7),
                UInt64(8),
            )
        )
        bin_ops()
        if non_empty_tuple():
            log("not empty")
        if (get_uint_with_side_effect(),):  # noqa: F634
            log("not empty2")
        return a + b

    def clear_state_program(self) -> UInt64:
        return UInt64(0)


@subroutine
def get_uint_with_side_effect() -> UInt64:
    log("get_uint_with_side_effect called")
    return UInt64(4)


@subroutine
def non_empty_tuple() -> tuple[UInt64, UInt64]:
    log("non_empty_tuple called")
    return UInt64(4), UInt64(2)


@subroutine
def bin_ops() -> None:
    a = (UInt64(1),) * 3
    assert a[0] == 1
    assert a[1] == 1
    assert a[2] == 1

    b = (UInt64(1),) + (Bytes(b"2"), UInt64(3))  # noqa: RUF005
    assert b[0] == 1
    assert b[1] == b"2"
    assert b[2] == 3


@subroutine
def bytes_combine(arg: tuple[Bytes, Bytes]) -> Bytes:
    a, b = arg
    result = a + b
    return result


@subroutine
def bytes_multiply(arg: tuple[Bytes, UInt64]) -> Bytes:
    b, count = arg
    result = Bytes()
    for _i in urange(count):
        result += b
    return result


@subroutine
def add_three_values(values: tuple[UInt64, UInt64, UInt64]) -> UInt64:
    total = UInt64(0)
    for value in values:
        total += value

    return total


@subroutine
def addw2(a: tuple[UInt64, UInt64], b: tuple[UInt64, UInt64]) -> tuple[UInt64, UInt64, UInt64]:
    a_hi, a_lo = a
    b_hi, b_lo = b
    lo_carry, c_lo = op.addw(a_lo, b_lo)
    hi_carry1, c_mid = op.addw(a_hi, b_hi)
    hi_carry2, c_mid = op.addw(c_mid, lo_carry)
    did_overflow, c_hi = op.addw(hi_carry1, hi_carry2)
    assert not did_overflow, "is such a thing even possible? 👽"
    return c_hi, c_mid, c_lo


@subroutine
def test_tuple_swap(zero: UInt64) -> None:
    a = zero + 1
    b = zero + 2
    (a, b) = (b, a)
    assert a == 2, "a should be two"
    assert b == 1, "b should be one"


@subroutine
def slicing(values: tuple[UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64]) -> None:
    one_to_three = values[0:3]
    assert add_three_values(one_to_three) == values[0] + values[1] + values[2]

    assert one_to_three[-2:-1][0] == one_to_three[1]
