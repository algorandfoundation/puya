# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class BranchElimination(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def umm(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def umm2(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def calculate(
        self,
        nested_list: algopy.arc4.DynamicArray[algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]],
        threshold: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
