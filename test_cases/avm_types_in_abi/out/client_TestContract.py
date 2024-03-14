# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class TestContract(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod(create=True)
    def create(
        self,
        bool_param: puyapy.arc4.Bool,
        uint64_param: puyapy.arc4.UInt64,
        bytes_param: puyapy.arc4.DynamicBytes,
        tuple_param: puyapy.arc4.Tuple[puyapy.arc4.Bool, puyapy.arc4.UInt64, puyapy.arc4.DynamicBytes],
    ) -> puyapy.arc4.Tuple[puyapy.arc4.Bool, puyapy.arc4.UInt64, puyapy.arc4.DynamicBytes]: ...

    @puyapy.arc4.abimethod
    def tuple_of_arc4(
        self,
        args: puyapy.arc4.Tuple[puyapy.arc4.UInt8, puyapy.arc4.Address],
    ) -> puyapy.arc4.Tuple[puyapy.arc4.UInt8, puyapy.arc4.Address]: ...
