# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class HelloOtherConstants(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(create='require')
    def create(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(allow_actions=['DeleteApplication'])
    def delete(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def greet(
        self,
        name: algopy.arc4.String,
    ) -> algopy.arc4.DynamicBytes: ...
