# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class EventEmitter(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod
    def emit_swapped(
        self,
        a: puyapy.arc4.UInt64,
        b: puyapy.arc4.UInt64,
    ) -> None: ...
