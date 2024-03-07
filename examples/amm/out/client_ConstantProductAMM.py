# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class ConstantProductAMM(puyapy.arc4.ARC4Client):
    @puyapy.arc4.abimethod
    def set_governor(
        self,
        new_governor: puyapy.Account,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def bootstrap(
        self,
        seed: puyapy.gtxn.PaymentTransaction,
        a_asset: puyapy.Asset,
        b_asset: puyapy.Asset,
    ) -> puyapy.arc4.UInt64:
        raise NotImplementedError

    @puyapy.arc4.abimethod(default_args={'pool_asset': 'pool_token', 'a_asset': 'asset_a', 'b_asset': 'asset_b'})
    def mint(
        self,
        a_xfer: puyapy.gtxn.AssetTransferTransaction,
        b_xfer: puyapy.gtxn.AssetTransferTransaction,
        pool_asset: puyapy.Asset,
        a_asset: puyapy.Asset,
        b_asset: puyapy.Asset,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod(default_args={'pool_asset': 'pool_token', 'a_asset': 'asset_a', 'b_asset': 'asset_b'})
    def burn(
        self,
        pool_xfer: puyapy.gtxn.AssetTransferTransaction,
        pool_asset: puyapy.Asset,
        a_asset: puyapy.Asset,
        b_asset: puyapy.Asset,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod(default_args={'a_asset': 'asset_a', 'b_asset': 'asset_b'})
    def swap(
        self,
        swap_xfer: puyapy.gtxn.AssetTransferTransaction,
        a_asset: puyapy.Asset,
        b_asset: puyapy.Asset,
    ) -> None:
        raise NotImplementedError
