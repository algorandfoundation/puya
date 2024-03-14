# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class Arc4DynamicStringArrayContract(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod
    def xyz(
        self,
    ) -> puyapy.arc4.DynamicArray[puyapy.arc4.String]: ...

    @puyapy.arc4.abimethod
    def xyz_raw(
        self,
    ) -> puyapy.arc4.DynamicArray[puyapy.arc4.String]: ...
