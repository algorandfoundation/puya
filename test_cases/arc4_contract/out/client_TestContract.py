# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TestContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_method(
        self,
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]:
        """
        Test method using @public decorator
        """
