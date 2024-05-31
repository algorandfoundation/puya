# ruff: noqa: SIM208, F403, F405
from algopy import *


class LiteralFolding(Contract):

    def approval_program(self) -> bool:
        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def unary_str(self) -> None:
        assert not ""
        assert not (not "abc")

    @subroutine
    def unary_bytes(self) -> None:
        assert not b""
        assert not (not b"abc")

    @subroutine
    def unary_int(self) -> None:
        assert not 0
        assert not (not 1)
        assert -1 == (0 - 1)
        assert +1 == (0 + 1)
        assert ~0 == -1

    @subroutine
    def unary_bool(self) -> None:
        assert not False
        assert not (not True)
        assert -True == -1
        assert +False == 0
        assert ~True == -2
