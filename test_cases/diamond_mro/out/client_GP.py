# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class GP(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(create='require')
    def create(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def method(
        self,
    ) -> None: ...
