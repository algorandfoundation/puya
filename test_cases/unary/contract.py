from algopy import (
    BigUInt,
    Bytes,
    Contract,
    UInt64,
    subroutine,
)

MAX_UINT64 = 2**64 - 1
MAX_BIGUINT = 2**512 - 1


class UnaryContract(Contract):
    def approval_program(self) -> bool:
        uint_unary()
        biguint_unary()
        bytes_unary()

        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine
def uint_unary() -> None:
    # test not
    assert not UInt64(0), "not uint"

    # test ~
    for i in (UInt64(1), UInt64(2), UInt64(150), UInt64(MAX_UINT64)):
        assert ~(MAX_UINT64 - i) == i, "~ uint"


@subroutine
def biguint_unary() -> None:
    # test not
    assert not BigUInt(0), "not biguint"


@subroutine
def bytes_unary() -> None:
    # test not
    assert not Bytes(b""), "not bytes"

    # test ~
    assert ~Bytes.from_hex("FF") == Bytes.from_hex("00"), "~ bytes"
    assert ~Bytes.from_hex("0000") == Bytes.from_hex("FFFF"), "~ bytes"
