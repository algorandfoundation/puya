# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class MerkleTree(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(create=True)
    def create(
        self,
        root: algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def verify(
        self,
        proof: algopy.arc4.DynamicArray[algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]]],
        leaf: algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[32]],
    ) -> algopy.arc4.Bool: ...
