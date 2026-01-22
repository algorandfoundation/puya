import typing

from algopy import Contract, UInt64, arc4, op, subroutine


class MyContract(Contract):
    def approval_program(self) -> bool:
        z = zero()
        a = one()
        b = one()
        assert z + a + b == 2
        never_returns()
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=True)
def never_returns() -> typing.Never:
    op.err("destined to fail")


@subroutine(inline=True)
def one() -> UInt64:
    return zero() + 1


@subroutine(inline=True)
def zero() -> UInt64:
    return UInt64(0)


ERR_MSG: typing.LiteralString = "always errors"


class NeverReturns(arc4.ARC4Contract):
    @arc4.abimethod()
    def err(self) -> None:
        op.err(ERR_MSG)
