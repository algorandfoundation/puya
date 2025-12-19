# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ContractTwo(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def renamed_some_method(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test(
        self,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod(resource_encoding='index')
    def reference_types_index(
        self,
        pay: algopy.gtxn.PaymentTransaction,
        asset: algopy.Asset,
        account: algopy.Account,
        app: algopy.Application,
        app_txn: algopy.gtxn.ApplicationCallTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def reference_types_value(
        self,
        pay: algopy.gtxn.PaymentTransaction,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        account: algopy.arc4.Address,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        app_txn: algopy.gtxn.ApplicationCallTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_tuple(
        self,
        val: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UFixedNxM[typing.Literal[64], typing.Literal[10]], algopy.arc4.StaticArray[algopy.arc4.UIntN[typing.Literal[64]], typing.Literal[3]], algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[32]]], algopy.arc4.Bool, algopy.arc4.Address, algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[16]]],
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UFixedNxM[typing.Literal[64], typing.Literal[10]], algopy.arc4.StaticArray[algopy.arc4.UIntN[typing.Literal[64]], typing.Literal[3]], algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[32]]], algopy.arc4.Bool, algopy.arc4.Address, algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[16]]]: ...
