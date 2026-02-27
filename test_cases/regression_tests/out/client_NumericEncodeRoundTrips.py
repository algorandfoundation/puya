# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class NumericEncodeRoundTrips(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def arc4_uint32_via_uint64(
        self,
        x: algopy.arc4.UIntN[typing.Literal[32]],
    ) -> algopy.arc4.UIntN[typing.Literal[32]]: ...

    @algopy.arc4.abimethod
    def arc4_uint64_via_uint64(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def arc4_uint128_via_uint64(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[128]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[128]]: ...

    @algopy.arc4.abimethod
    def uint64_via_arc4_uint32(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def uint64_via_arc4_uint64(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def uint64_via_arc4_uint128(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def arc4_uint32_via_biguint(
        self,
        x: algopy.arc4.UIntN[typing.Literal[32]],
    ) -> algopy.arc4.UIntN[typing.Literal[32]]: ...

    @algopy.arc4.abimethod
    def arc4_uint64_via_biguint(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def arc4_uint128_via_biguint(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[128]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[128]]: ...

    @algopy.arc4.abimethod
    def biguint_via_arc4_uint32(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def biguint_via_arc4_uint64(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def biguint_via_arc4_uint128(
        self,
        x: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...
