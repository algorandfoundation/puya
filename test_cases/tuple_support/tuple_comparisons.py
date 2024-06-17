from algopy import Contract, String, UInt64, log, subroutine


class TupleComparisons(Contract):
    def approval_program(self) -> bool:
        test_tuple_cmp_eval()
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
    assert (UInt64(1), UInt64(2)) != (UInt64(3), log_and_return(UInt64(43)))
    tmp = (UInt64(1), UInt64(2)) == (UInt64(3), log_and_return(UInt64(44)))
    assert not tmp


@subroutine
def log_and_return(val: UInt64) -> UInt64:
    log(val)
    return val
