# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class FixedSizeContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_array(
        self,
        x1: algopy.arc4.UIntN[typing.Literal[64]],
        y1: algopy.arc4.UIntN[typing.Literal[64]],
        x2: algopy.arc4.UIntN[typing.Literal[64]],
        y2: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
