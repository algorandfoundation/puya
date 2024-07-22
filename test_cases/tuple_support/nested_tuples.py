from algopy import Contract, String, UInt64, op, subroutine


class NestedTuples(Contract):
    def approval_program(self) -> bool:
        x = (String("Hi"), String("There"))
        assert test_swap(x) == (String("There"), String("Hi"))
        y = (UInt64(1), x)
        z = (UInt64(0), UInt64(2), y)

        (a, b, (c, d, (e,))) = test_rearrange(z)
        assert (a, b) == (String("Hi"), UInt64(0))
        assert (c, d) == (UInt64(2), UInt64(1))
        assert e == String("There")

        test_intrinsics(UInt64(1), UInt64(2))

        assert z[2] == y

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def test_rearrange(
    args: tuple[UInt64, UInt64, tuple[UInt64, tuple[String, String]]]
) -> tuple[String, UInt64, tuple[UInt64, UInt64, tuple[String]]]:
    (a, b, (c, (d, e))) = args

    return d, a, (b, c, (e,))


@subroutine
def test_swap(args: tuple[String, String]) -> tuple[String, String]:
    (a, b) = args
    return b, a


@subroutine
def test_intrinsics(num1: UInt64, num2: UInt64) -> None:
    nt = (UInt64(1), op.addw(num1, num2))
