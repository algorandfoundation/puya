from algopy import Contract, String, UInt64, op, subroutine


class NestedTuples(Contract):
    def approval_program(self) -> bool:
        x = (String("Hi"), String("There"))
        assert test_swap(x) == (String("There"), String("Hi"))
        y = (UInt64(1), x)
        z = (UInt64(0), UInt64(2), y)
        z2 = z[2]
        z2_1 = z2[1]
        _x, z2_1_1 = z2_1
        assert z2_1_1 == "There"

        (a, b, (c, d, (e,))) = test_rearrange(z)
        assert (a, b) == (String("Hi"), UInt64(0))
        assert (c, d) == (UInt64(2), UInt64(1))
        assert e == String("There")

        test_intrinsics(UInt64(1), UInt64(2))
        test_nested_slicing()

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
    nt = (UInt64(1), op.addw(num1, num2), UInt64(42))
    assert nt[0] == 1
    assert nt[-1] == 42
    assert nt[1] == (0, num1 + num2)  # type: ignore[comparison-overlap]
    assert nt[1][:1] == (0,)  # type: ignore[comparison-overlap]
    assert nt[1][1:] == (num1 + num2,)
    ((x, y),) = nt[1:2]
    assert x == 0
    assert y == num1 + num2


@subroutine
def test_nested_slicing() -> None:
    nt = (
        UInt64(1),
        UInt64(2),
        (
            UInt64(3),
            (
                String("a"),
                String("b"),
            ),
            UInt64(4),
        ),
        UInt64(5),
        UInt64(6),
    )
    (a, b, c) = nt[1:4]
    assert b[-1] == 4
    assert ((a, c),) == ((2, 5),)  # type: ignore[comparison-overlap]
    assert b[1][:] == ("a", "b")  # type: ignore[comparison-overlap]
