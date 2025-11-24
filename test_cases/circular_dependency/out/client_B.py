# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class B(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def ping(
        self,
    ) -> algopy.arc4.String: ...

    @algopy.arc4.abimethod
    def pong(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.String: ...

    @algopy.arc4.abimethod
    def create_a(
        self,
        factory_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
