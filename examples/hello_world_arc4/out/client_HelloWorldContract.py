# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class HelloWorldContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def hello(
        self,
        name: algopy.arc4.String,
    ) -> algopy.arc4.String: ...
