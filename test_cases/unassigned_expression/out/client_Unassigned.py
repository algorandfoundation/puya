# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Unassigned(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def discard_op(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def discard_subroutine(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def discard_constants(
        self,
    ) -> None: ...
