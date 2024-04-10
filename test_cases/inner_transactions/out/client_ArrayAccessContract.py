# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ArrayAccessContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_branching_array_call(
        self,
        maybe: algopy.arc4.Bool,
    ) -> None: ...
