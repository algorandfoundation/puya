# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class Logger(puyapy.arc4.ARC4Client):
    @puyapy.arc4.abimethod
    def echo(
        self,
        value: puyapy.arc4.String,
    ) -> puyapy.arc4.String:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_uint64(
        self,
        value: puyapy.arc4.UInt64,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_uint512(
        self,
        value: puyapy.arc4.UInt512,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_string(
        self,
        value: puyapy.arc4.String,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_bool(
        self,
        value: puyapy.arc4.Bool,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_bytes(
        self,
        value: puyapy.arc4.DynamicBytes,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def log_asset_account_app(
        self,
        asset: puyapy.Asset,
        account: puyapy.Account,
        app: puyapy.Application,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def return_args_after_14th(
        self,
        _a1: puyapy.arc4.UInt64,
        _a2: puyapy.arc4.UInt64,
        _a3: puyapy.arc4.UInt64,
        _a4: puyapy.arc4.UInt64,
        _a5: puyapy.arc4.UInt64,
        _a6: puyapy.arc4.UInt64,
        _a7: puyapy.arc4.UInt64,
        _a8: puyapy.arc4.UInt64,
        _a9: puyapy.arc4.UInt64,
        _a10: puyapy.arc4.UInt64,
        _a11: puyapy.arc4.UInt64,
        _a12: puyapy.arc4.UInt64,
        _a13: puyapy.arc4.UInt64,
        _a14: puyapy.arc4.UInt64,
        a15: puyapy.arc4.UInt8,
        a16: puyapy.arc4.UInt8,
        a17: puyapy.arc4.UInt8,
        a18: puyapy.arc4.UInt8,
        a19: puyapy.arc4.Tuple[puyapy.arc4.UInt8, puyapy.arc4.UInt8, puyapy.arc4.UInt8, puyapy.arc4.UInt8],
        a20: puyapy.arc4.UInt8,
    ) -> puyapy.arc4.DynamicBytes:
        raise NotImplementedError
