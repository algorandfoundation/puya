# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class OneConstSimplificationContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    GVN one-const algebraic simplifications that collapse to a value or operand.

        Each method passes a runtime value in and returns the simplified result, so
        the pytest test can assert the rewrite preserved semantics. The interesting
        operand is a constant (0/1) that GVN sees, triggering a one-const rule in
        `simplify_uint64_binary_op_one_const` / `simplify_bytes_binary_op_one_const`.
    
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
