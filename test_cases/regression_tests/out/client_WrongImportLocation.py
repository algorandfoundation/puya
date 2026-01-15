# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class WrongImportLocation(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def verify(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
