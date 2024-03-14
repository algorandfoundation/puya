# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class MerkleTree(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod(create=True)
    def create(
        self,
        root: puyapy.arc4.StaticArray[puyapy.arc4.Byte, typing.Literal[32]],
    ) -> None: ...

    @puyapy.arc4.abimethod
    def verify(
        self,
        proof: puyapy.arc4.DynamicArray[puyapy.arc4.StaticArray[puyapy.arc4.Byte, typing.Literal[32]]],
        leaf: puyapy.arc4.StaticArray[puyapy.arc4.Byte, typing.Literal[32]],
    ) -> puyapy.arc4.Bool: ...
