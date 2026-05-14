# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class BoxReadCache(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def repro(
        self,
    ) -> algopy.arc4.Tuple[algopy.arc4.Bool, algopy.arc4.Bool, algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]: ...
