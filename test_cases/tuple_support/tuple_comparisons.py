from algopy import Contract, String, UInt64, log, subroutine


class TupleComparisons(Contract):
    def approval_program(self) -> bool:
        test_tuple_cmp_eval()
        test_tuple_cmp_empty()
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def test_tuple_cmp_eval() -> None:
    assert (
        String("abc"),
        log_and_return(UInt64(42)),
    ) != (
        String("abc"),
    )  # type: ignore[comparison-overlap]
    tmp = (
        String("abc"),
        log_and_return(UInt64(43)),
    ) == (
        String("abc"),
    )  # type: ignore[comparison-overlap]
    assert not tmp

    assert (String("abc"),) != (
        String("abc"),
        log_and_return(UInt64(44)),
    )  # type: ignore[comparison-overlap]
    tmp = (String("abc"),) == (
        String("abc"),
        log_and_return(UInt64(45)),
    )  # type: ignore[comparison-overlap]
    assert not tmp

    assert (UInt64(1), UInt64(2)) != (UInt64(3), log_and_return(UInt64(46)))
    tmp = (UInt64(1), UInt64(2)) == (UInt64(3), log_and_return(UInt64(47)))
    assert not tmp


@subroutine
def test_tuple_cmp_empty() -> None:
    assert () == ()
    tmp = () != ()
    assert not tmp

    assert () != ("a",)  # type: ignore[comparison-overlap]
    tmp = () == ("a",)  # type: ignore[comparison-overlap]
    assert not tmp


@subroutine
def log_and_return(val: UInt64) -> UInt64:
    log(val)
    return val
