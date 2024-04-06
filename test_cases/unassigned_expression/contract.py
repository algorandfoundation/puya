from algopy import ARC4Contract, Bytes, UInt64, arc4, op, subroutine


class Unassigned(ARC4Contract):
    @arc4.abimethod()
    def discard_op(self) -> None:
        op.bzero(10)

    @arc4.abimethod()
    def discard_subroutine(self) -> None:
        get_a_value()

    @arc4.abimethod()
    def discard_constants(self) -> None:
        Bytes()
        UInt64()
        True  # noqa: B018


@subroutine
def get_a_value() -> UInt64:
    return UInt64(42)
