# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class NeverReturnsFStack(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def method(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
