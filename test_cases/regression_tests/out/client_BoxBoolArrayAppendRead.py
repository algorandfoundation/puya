# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class BoxBoolArrayAppendRead(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Regression test: appending to a dynamic array of bools stored in a box was lowered
        to an in-place helper that advanced one byte per element, while reads of the same
        array are (correctly) bit packed. After two appends the box contained
        `[len=2][0x80][0x80]` and reading index 1 returned the (zero) bit 1 of the first byte,
        so `push(true); push(true)` read back as `[true, false]`.
    """
    @algopy.arc4.abimethod
    def box_push_read(
        self,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def box_round_trip(
        self,
        n: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def box_access(
        self,
        index: algopy.arc4.UIntN[typing.Literal[64]],
        write: algopy.arc4.Bool,
    ) -> algopy.arc4.Bool: ...
