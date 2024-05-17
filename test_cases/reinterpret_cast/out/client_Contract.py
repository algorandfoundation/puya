# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def bytes_to_bool(
        self,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def test_bytes_to_biguint(
        self,
    ) -> None: ...
