from algopy import BigUInt, Contract, Txn, UInt64, op, subroutine


class BigUIntContract(Contract):
    def approval_program(self) -> bool:
        one = BigUInt(1)
        compare_biguints(one, BigUInt(2))
        compare_biguint_vs_uint64(one, UInt64(2))
        compare_uint64_vs_biguint(UInt64(1), BigUInt(2))
        assert BigUInt(1 if Txn.num_app_args else 5) == 5, "constructor expressions supported"
        assert op.bsqrt(BigUInt(9)) == op.bsqrt(10)
        assert one == +one
        return True

    def clear_state_program(self) -> bool:
        assert BigUInt() == 0
        return True


@subroutine
def compare_biguints(one: BigUInt, two: BigUInt) -> None:
    assert one < two
    assert one <= two
    assert one == one  # noqa: PLR0124
    assert two > one
    assert two >= one
    assert one != two


@subroutine
def compare_biguint_vs_uint64(one: BigUInt, two: UInt64) -> None:
    assert one < two
    assert one <= two
    assert one == one  # noqa: PLR0124
    assert two > one
    assert two >= one
    assert one != two


@subroutine
def compare_uint64_vs_biguint(one: UInt64, two: BigUInt) -> None:
    assert one < two
    assert one <= two
    assert one == one  # noqa: PLR0124
    assert two > one
    assert two >= one
    assert one != two
