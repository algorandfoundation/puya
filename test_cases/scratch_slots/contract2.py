import typing

import algopy
from algopy import Bytes, UInt64, op, subroutine, urange

from test_cases.scratch_slots.contract import MyContract

RenamedURange: typing.TypeAlias = urange


class MyContract2(
    MyContract,
    scratch_slots=[5, 25, urange(50, 53, 2), RenamedURange(100, 105), algopy.urange(110, 115)],
):
    @subroutine
    def my_sub(self) -> None:
        op.Scratch.store(UInt64(1), Bytes(b"abc"))

        op.Scratch.store(52, Bytes(b"52"))
