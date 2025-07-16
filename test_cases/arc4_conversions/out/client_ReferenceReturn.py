# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ReferenceReturn(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def acc_ret(
        self,
    ) -> algopy.arc4.Address: ...

    @algopy.arc4.abimethod
    def asset_ret(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def app_ret(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def store(
        self,
        acc: algopy.arc4.Address,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        asset: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def store_apps(
        self,
        apps: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def store_assets(
        self,
        assets: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def store_accounts(
        self,
        accounts: algopy.arc4.DynamicArray[algopy.arc4.Address],
    ) -> None: ...

    @algopy.arc4.abimethod
    def return_apps(
        self,
    ) -> algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def return_assets(
        self,
    ) -> algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def return_accounts(
        self,
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Address]: ...
