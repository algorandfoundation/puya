# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Receiver(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def receive_bools(
        self,
        b: algopy.arc4.DynamicArray[algopy.arc4.Bool],
    ) -> None: ...

    @algopy.arc4.abimethod(allow_actions=['DeleteApplication'])
    def delete(
        self,
    ) -> None: ...
