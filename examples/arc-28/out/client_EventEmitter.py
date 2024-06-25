# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class EventEmitter(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def emit_swapped(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
