# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class FixedBytesABI(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_passing_fixed_bytes(
        self,
    ) -> None: ...
