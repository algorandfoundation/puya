# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class Reference(puyapy.arc4.ARC4Client):
    @puyapy.arc4.abimethod
    def noop_with_uint64(
        self,
        a: puyapy.arc4.UInt64,
    ) -> puyapy.arc4.UInt8:
        raise NotImplementedError

    @puyapy.arc4.abimethod(name='all_the_things', readonly=True, allow_actions=['NoOp', 'OptIn', 'CloseOut', 'UpdateApplication', 'DeleteApplication'], create='allow')
    def full_abi_config(
        self,
        a: puyapy.arc4.UInt64,
    ) -> puyapy.arc4.UInt8:
        raise NotImplementedError

    @puyapy.arc4.abimethod(readonly=True, allow_actions=['NoOp', 'CloseOut', 'DeleteApplication'])
    def mixed_oca(
        self,
        a: puyapy.arc4.UInt64,
    ) -> puyapy.arc4.UInt8:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def opt_into_asset(
        self,
        asset: puyapy.Asset,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def with_transactions(
        self,
        asset: puyapy.Asset,
        an_int: puyapy.arc4.UInt64,
        pay: puyapy.gtxn.PaymentTransaction,
        another_int: puyapy.arc4.UInt64,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def compare_assets(
        self,
        asset_a: puyapy.Asset,
        asset_b: puyapy.Asset,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod(readonly=True)
    def get_address(
        self,
    ) -> puyapy.arc4.Address:
        raise NotImplementedError

    @puyapy.arc4.abimethod(readonly=True)
    def get_asset(
        self,
    ) -> puyapy.arc4.UInt64:
        raise NotImplementedError

    @puyapy.arc4.abimethod(name='get_application', readonly=True)
    def get_app(
        self,
    ) -> puyapy.arc4.UInt64:
        raise NotImplementedError

    @puyapy.arc4.abimethod(name='get_an_int', readonly=True)
    def get_a_int(
        self,
    ) -> puyapy.arc4.UInt64:
        raise NotImplementedError

    @puyapy.arc4.abimethod(default_args={'asset_from_storage': 'asa', 'asset_from_function': 'get_asset', 'account_from_storage': 'creator', 'account_from_function': 'get_address', 'application_from_storage': 'app', 'application_from_function': 'get_app', 'bytes_from_storage': 'some_bytes', 'int_from_storage': 'an_int', 'int_from_function': 'get_a_int'})
    def method_with_default_args(
        self,
        asset_from_storage: puyapy.Asset,
        asset_from_function: puyapy.Asset,
        account_from_storage: puyapy.Account,
        account_from_function: puyapy.Account,
        application_from_storage: puyapy.Application,
        application_from_function: puyapy.Application,
        bytes_from_storage: puyapy.arc4.StaticArray[puyapy.arc4.Byte, typing.Literal[3]],
        int_from_storage: puyapy.arc4.UInt64,
        int_from_function: puyapy.arc4.UInt64,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def method_with_more_than_15_args(
        self,
        a: puyapy.arc4.UInt64,
        b: puyapy.arc4.UInt64,
        c: puyapy.arc4.UInt64,
        d: puyapy.arc4.UInt64,
        asset: puyapy.Asset,
        e: puyapy.arc4.UInt64,
        f: puyapy.arc4.UInt64,
        pay: puyapy.gtxn.PaymentTransaction,
        g: puyapy.arc4.UInt64,
        h: puyapy.arc4.UInt64,
        i: puyapy.arc4.UInt64,
        j: puyapy.arc4.UInt64,
        k: puyapy.arc4.UInt64,
        l: puyapy.arc4.UInt64,
        m: puyapy.arc4.UInt64,
        n: puyapy.arc4.UInt64,
        o: puyapy.arc4.UInt64,
        p: puyapy.arc4.UInt64,
        q: puyapy.arc4.UInt64,
        r: puyapy.arc4.UInt64,
        s: puyapy.arc4.DynamicBytes,
        t: puyapy.arc4.DynamicBytes,
        asset2: puyapy.Asset,
        pay2: puyapy.gtxn.PaymentTransaction,
        u: puyapy.arc4.UInt64,
        v: puyapy.arc4.UInt64,
    ) -> puyapy.arc4.UInt64:
        raise NotImplementedError
