# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class MyContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(create='require')
    def create(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod(allow_actions=['NoOp', 'OptIn'])
    def register(
        self,
        name: algopy.arc4.String,
    ) -> None: ...

    @algopy.arc4.abimethod
    def say_hello(
        self,
    ) -> algopy.arc4.String: ...

    @algopy.arc4.abimethod
    def calculate(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(allow_actions=['CloseOut'])
    def close_out(
        self,
    ) -> None: ...
