# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class DeclinedConstFoldContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Ops where GVN sees constant operands but declines to fold because the op would
        trap at runtime — exercising the decline (`return None`) branches of the fold helpers.
        Zero divisors are built via btoi/bzero so the frontend doesn't reject them while GVN
        still proves them constant.
    
    """
    @algopy.arc4.abimethod
    def expw_zero_zero(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def expw_overflow(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def divw_div_zero(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def divw_overflow(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def divmodw_div_zero(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def setbyte_value_oob(
        self,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def bsqrt_too_long(
        self,
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def div_by_zero(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def mod_by_zero(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def biguint_mod_by_zero(
        self,
    ) -> algopy.arc4.BigUIntN[typing.Literal[256]]: ...
