# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Verifier(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def verify(
        self,
        proof: algopy.arc4.DynamicArray[algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]]],
    ) -> algopy.arc4.DynamicBytes: ...
