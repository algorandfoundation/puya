# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Simplifications(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def select_neq(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def chained_extract(
        self,
        src: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def biguint_add_fold(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def biguint_mul_fold(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def biguint_add_no_fold(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
        y: algopy.arc4.BigUIntN[typing.Literal[512]],
        z: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def biguint_add_bytes_const(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def biguint_add_oversized(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def biguint_add_double_oversized(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
        y: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...
