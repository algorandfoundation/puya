# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class CheckABIApp(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def manual_validate(
        self,
        value: algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[11]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def router_validate(
        self,
        value: algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[11]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def i_am_a_dynamic_personality(
        self,
        value: algopy.arc4.DynamicBytes,
    ) -> None: ...
