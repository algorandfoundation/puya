# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Greeter(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def bootstrap(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def log_greetings(
        self,
        name: algopy.arc4.String,
    ) -> None: ...
