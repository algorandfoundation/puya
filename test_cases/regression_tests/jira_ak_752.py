# https://algorandfoundation.atlassian.net/browse/AK-752

import typing

import algopy
from algopy import arc4
from algopy.arc4 import DynamicArray, StaticArray, abimethod

Bytes32: typing.TypeAlias = StaticArray[arc4.Byte, typing.Literal[32]]


class Verifier(algopy.ARC4Contract):
    @abimethod
    def verify(
        self,
        proof: DynamicArray[Bytes32],
    ) -> algopy.Bytes:
        x = proof[8].bytes  # ok
        y = proof[6].bytes + proof[7].bytes  # ok
        z = proof[7].bytes + proof[8].bytes  # Invalid immediate, expected value between 0 and 255

        return x + y + z
