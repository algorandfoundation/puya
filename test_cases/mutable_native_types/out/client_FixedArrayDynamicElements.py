# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class Data(algopy.arc4.Struct):
    timestamp: algopy.arc4.UIntN[typing.Literal[64]]
    value: algopy.arc4.String

class FixedArrayDynamicElements(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def write_at_index(
        self,
        index: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.String,
    ) -> None: ...

    @algopy.arc4.abimethod
    def read_at_index(
        self,
        index: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> Data: ...
