# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class TemplateVariablesContract(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod
    def get_bytes(
        self,
    ) -> puyapy.arc4.DynamicBytes: ...

    @puyapy.arc4.abimethod
    def get_big_uint(
        self,
    ) -> puyapy.arc4.UInt512: ...
