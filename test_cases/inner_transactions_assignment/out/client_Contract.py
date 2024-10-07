# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_itxn_slice(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_itxn_nested(
        self,
    ) -> None: ...
