# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Reference(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def noop_with_uint64(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[8]]: ...

    @algopy.arc4.abimethod(name='all_the_things', readonly=True, allow_actions=['NoOp', 'OptIn', 'CloseOut', 'UpdateApplication', 'DeleteApplication'], create='allow')
    def full_abi_config(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[8]]: ...

    @algopy.arc4.abimethod(readonly=True, allow_actions=['NoOp', 'CloseOut', 'DeleteApplication'])
    def mixed_oca(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[8]]: ...

    @algopy.arc4.abimethod
    def opt_into_asset(
        self,
        asset: algopy.Asset,
    ) -> None: ...

    @algopy.arc4.abimethod
    def with_transactions(
        self,
        asset: algopy.Asset,
        an_int: algopy.arc4.UIntN[typing.Literal[64]],
        pay: algopy.gtxn.PaymentTransaction,
        another_int: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def compare_assets(
        self,
        asset_a: algopy.Asset,
        asset_b: algopy.Asset,
    ) -> None: ...

    @algopy.arc4.abimethod(readonly=True)
    def get_address(
        self,
    ) -> algopy.arc4.Address: ...

    @algopy.arc4.abimethod(readonly=True)
    def get_asset(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(name='get_application', readonly=True)
    def get_app(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(name='get_an_int', readonly=True)
    def get_a_int(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(default_args={'asset_from_storage': 'asa', 'asset_from_function': 'get_asset', 'account_from_storage': 'creator', 'account_from_function': 'get_address', 'application_from_storage': 'app', 'application_from_function': 'get_app', 'bytes_from_storage': 'some_bytes', 'int_from_storage': 'an_int', 'int_from_function': 'get_a_int'})
    def method_with_default_args(
        self,
        asset_from_storage: algopy.Asset,
        asset_from_function: algopy.Asset,
        account_from_storage: algopy.Account,
        account_from_function: algopy.Account,
        application_from_storage: algopy.Application,
        application_from_function: algopy.Application,
        bytes_from_storage: algopy.arc4.StaticArray[algopy.arc4.Byte, typing.Literal[3]],
        int_from_storage: algopy.arc4.UIntN[typing.Literal[64]],
        int_from_function: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def method_with_more_than_15_args(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.UIntN[typing.Literal[64]],
        c: algopy.arc4.UIntN[typing.Literal[64]],
        d: algopy.arc4.UIntN[typing.Literal[64]],
        asset: algopy.Asset,
        e: algopy.arc4.UIntN[typing.Literal[64]],
        f: algopy.arc4.UIntN[typing.Literal[64]],
        pay: algopy.gtxn.PaymentTransaction,
        g: algopy.arc4.UIntN[typing.Literal[64]],
        h: algopy.arc4.UIntN[typing.Literal[64]],
        i: algopy.arc4.UIntN[typing.Literal[64]],
        j: algopy.arc4.UIntN[typing.Literal[64]],
        k: algopy.arc4.UIntN[typing.Literal[64]],
        l: algopy.arc4.UIntN[typing.Literal[64]],
        m: algopy.arc4.UIntN[typing.Literal[64]],
        n: algopy.arc4.UIntN[typing.Literal[64]],
        o: algopy.arc4.UIntN[typing.Literal[64]],
        p: algopy.arc4.UIntN[typing.Literal[64]],
        q: algopy.arc4.UIntN[typing.Literal[64]],
        r: algopy.arc4.UIntN[typing.Literal[64]],
        s: algopy.arc4.DynamicBytes,
        t: algopy.arc4.DynamicBytes,
        asset2: algopy.Asset,
        pay2: algopy.gtxn.PaymentTransaction,
        u: algopy.arc4.UIntN[typing.Literal[64]],
        v: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def hello_with_algopy_string(
        self,
        name: algopy.arc4.String,
    ) -> algopy.arc4.String: ...
