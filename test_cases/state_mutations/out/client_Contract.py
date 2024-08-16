# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def append(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def modify(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def get(
        self,
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.String]]: ...
