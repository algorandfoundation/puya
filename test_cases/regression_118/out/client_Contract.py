# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class Contract(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod
    def verify(
        self,
        values: puyapy.arc4.DynamicArray[puyapy.arc4.UInt256],
    ) -> puyapy.arc4.Tuple[puyapy.arc4.Bool, puyapy.arc4.String]: ...
