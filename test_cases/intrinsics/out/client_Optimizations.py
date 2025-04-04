# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Optimizations(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def sha256(
        self,
    ) -> algopy.arc4.DynamicBytes: ...
