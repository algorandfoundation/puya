# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class FieldTupleContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_assign_tuple(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_assign_tuple_mixed(
        self,
    ) -> None: ...
