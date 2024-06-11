# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class LargeProgram(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def get_big_bytes_length(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(allow_actions=['DeleteApplication'])
    def delete(
        self,
    ) -> None: ...
