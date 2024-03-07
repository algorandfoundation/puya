# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class Greeter(puyapy.arc4.ARC4Client):
    @puyapy.arc4.abimethod
    def bootstrap(
        self,
    ) -> puyapy.arc4.UInt64:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_greetings(
        self,
        name: puyapy.arc4.String,
    ) -> None:
        raise NotImplementedError
