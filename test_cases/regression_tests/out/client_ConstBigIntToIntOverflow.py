# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ConstBigIntToIntOverflow(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def get_abs_bound1(
        self,
        upper_bound: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def get_abs_bound2(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
