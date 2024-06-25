# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Logger(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def echo(
        self,
        value: algopy.arc4.String,
    ) -> algopy.arc4.String: ...

    @algopy.arc4.abimethod(name='log')
    def log_uint64(
        self,
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log_uint512(
        self,
        value: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log_string(
        self,
        value: algopy.arc4.String,
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log_bool(
        self,
        value: algopy.arc4.Bool,
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log_bytes(
        self,
        value: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log_asset_account_app(
        self,
        asset: algopy.Asset,
        account: algopy.Account,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def echo_native_string(
        self,
        value: algopy.arc4.String,
    ) -> algopy.arc4.String: ...

    @algopy.arc4.abimethod
    def echo_native_bytes(
        self,
        value: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def echo_native_uint64(
        self,
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def echo_native_biguint(
        self,
        value: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def echo_native_tuple(
        self,
        s: algopy.arc4.String,
        b: algopy.arc4.DynamicBytes,
        u: algopy.arc4.UIntN[typing.Literal[64]],
        bu: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.Tuple[algopy.arc4.String, algopy.arc4.DynamicBytes, algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.BigUIntN[typing.Literal[512]]]: ...

    @algopy.arc4.abimethod
    def return_args_after_14th(
        self,
        _a1: algopy.arc4.UIntN[typing.Literal[64]],
        _a2: algopy.arc4.UIntN[typing.Literal[64]],
        _a3: algopy.arc4.UIntN[typing.Literal[64]],
        _a4: algopy.arc4.UIntN[typing.Literal[64]],
        _a5: algopy.arc4.UIntN[typing.Literal[64]],
        _a6: algopy.arc4.UIntN[typing.Literal[64]],
        _a7: algopy.arc4.UIntN[typing.Literal[64]],
        _a8: algopy.arc4.UIntN[typing.Literal[64]],
        _a9: algopy.arc4.UIntN[typing.Literal[64]],
        _a10: algopy.arc4.UIntN[typing.Literal[64]],
        _a11: algopy.arc4.UIntN[typing.Literal[64]],
        _a12: algopy.arc4.UIntN[typing.Literal[64]],
        _a13: algopy.arc4.UIntN[typing.Literal[64]],
        _a14: algopy.arc4.UIntN[typing.Literal[64]],
        a15: algopy.arc4.UIntN[typing.Literal[8]],
        a16: algopy.arc4.UIntN[typing.Literal[8]],
        a17: algopy.arc4.UIntN[typing.Literal[8]],
        a18: algopy.arc4.UIntN[typing.Literal[8]],
        a19: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[8]], algopy.arc4.UIntN[typing.Literal[8]], algopy.arc4.UIntN[typing.Literal[8]], algopy.arc4.UIntN[typing.Literal[8]]],
        a20: algopy.arc4.UIntN[typing.Literal[8]],
    ) -> algopy.arc4.DynamicBytes: ...
