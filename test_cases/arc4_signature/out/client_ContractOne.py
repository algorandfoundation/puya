# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ContractOne(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def some_method(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_reference_types(
        self,
    ) -> None: ...
