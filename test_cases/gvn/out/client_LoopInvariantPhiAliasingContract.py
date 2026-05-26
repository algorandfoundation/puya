# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class LoopInvariantPhiAliasingContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def run(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
        y: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
