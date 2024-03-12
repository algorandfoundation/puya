# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class MyContract(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod(create=True)
    def create(
        self,
    ) -> None: ...

    @puyapy.arc4.abimethod(allow_actions=['NoOp', 'OptIn'])
    def register(
        self,
        name: puyapy.arc4.String,
    ) -> None: ...

    @puyapy.arc4.abimethod
    def say_hello(
        self,
    ) -> puyapy.arc4.String: ...

    @puyapy.arc4.abimethod
    def calculate(
        self,
        a: puyapy.arc4.UInt64,
        b: puyapy.arc4.UInt64,
    ) -> puyapy.arc4.UInt64: ...

    @puyapy.arc4.abimethod(allow_actions=['CloseOut'])
    def close_out(
        self,
    ) -> None: ...
