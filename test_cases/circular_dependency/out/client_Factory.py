# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Factory(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def deploy_a(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def deploy_b(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
