import typing

from algopy import Contract, op, subroutine


class MyContract(Contract):
    def approval_program(self) -> bool:
        never_returns()
        return True

    def clear_state_program(self) -> bool:
        return True


@subroutine(inline=True)
def never_returns() -> typing.Never:
    op.err()
