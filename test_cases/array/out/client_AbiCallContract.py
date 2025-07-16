# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class AbiCallContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_implicit_conversion_abi_call(
        self,
        arr: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
