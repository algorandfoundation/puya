from puyapy import BigUInt, Contract, UInt64, subroutine


class BigUIntContract(Contract):
    def approval_program(self) -> bool:
        compare_biguints(BigUInt(1), BigUInt(2))
        compare_biguint_vs_uint64(BigUInt(1), UInt64(2))
        compare_uint64_vs_biguint(UInt64(1), BigUInt(2))
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
