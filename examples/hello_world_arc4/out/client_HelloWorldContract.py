# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class HelloWorldContract(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod
    def hello(
        self,
        name: puyapy.arc4.String,
    ) -> puyapy.arc4.String: ...
