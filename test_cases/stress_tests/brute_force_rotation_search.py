from algopy import Contract, UInt64, subroutine


class BruteForceRotationSearch(Contract):
    def approval_program(self) -> bool:
        (
            a,
            b,
            c,
            d,
            e,
            f,
            g,
            h,
            i,
            j,
            k,
            l,  # noqa: E741
            m,
            n,
        ) = do_some_ops(UInt64(0), UInt64(0))

        assert a == 0
        assert b == 1
        assert c == 2
        assert d == 3
        assert e == 4
        assert f == 5
        assert g == 6
        assert h == 7
        assert i == 8
        assert j == 9
        assert k == 10
        assert l == 11
        assert m == 12
        assert n == 13
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def do_some_ops(
    a: UInt64, b: UInt64
) -> tuple[
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
    UInt64,
]:
    c = a + b
    return (
        c,
        c + 1,
        c + 2,
        c + 3,
        c + 4,
        c + 5,
        c + 6,
        c + 7,
        c + 8,
        c + 9,
        c + 10,
        c + 11,
        c + 12,
        c + 13,
    )
