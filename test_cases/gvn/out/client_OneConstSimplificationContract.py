# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class OneConstSimplificationContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    GVN one-const algebra: an op with one constant operand (0 or 1) collapses to a
        value or to the other operand, in both branch-condition and value contexts. The
        `UInt64(...)` wrappers are load-bearing — without them the puyapy frontend flips the
        literal around (correct, but bypasses the lines under test).
    
    """
    @algopy.arc4.abimethod
    def mul_zero(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def gt_zero(
        self,
        b: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def lte_one(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def or_false(
        self,
        a: algopy.arc4.Bool,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def bmul_zero(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[256]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[256]]: ...

    @algopy.arc4.abimethod
    def badd_zero_left(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[256]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[256]]: ...

    @algopy.arc4.abimethod
    def badd_zero_right(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[256]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[256]]: ...

    @algopy.arc4.abimethod
    def bsub_zero(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[256]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[256]]: ...

    @algopy.arc4.abimethod
    def bdiv_one(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[256]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[256]]: ...

    @algopy.arc4.abimethod
    def cond_gt_zero(
        self,
        b: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def val_lte_one(
        self,
        b: algopy.arc4.Bool,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def val_lt_zero(
        self,
        b: algopy.arc4.Bool,
    ) -> algopy.arc4.Bool: ...
