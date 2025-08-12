# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class BoolOnly(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def set_0_convert(
        self,
        inp: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def set_0_compare(
        self,
        inp: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def bool_only_properties(
        self,
    ) -> None: ...
