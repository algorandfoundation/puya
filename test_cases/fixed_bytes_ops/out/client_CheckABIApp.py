# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class CheckABIApp(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def check_fixed_bytes(
        self,
        value: algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[11]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...
