# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ConstantProductAMM(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def set_governor(
        self,
        new_governor: algopy.Account,
    ) -> None: ...

    @algopy.arc4.abimethod
    def bootstrap(
        self,
        seed: algopy.gtxn.PaymentTransaction,
        a_asset: algopy.Asset,
        b_asset: algopy.Asset,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(default_args={'pool_asset': 'pool_token', 'a_asset': 'asset_a', 'b_asset': 'asset_b'})
    def mint(
        self,
        a_xfer: algopy.gtxn.AssetTransferTransaction,
        b_xfer: algopy.gtxn.AssetTransferTransaction,
        pool_asset: algopy.Asset,
        a_asset: algopy.Asset,
        b_asset: algopy.Asset,
    ) -> None: ...

    @algopy.arc4.abimethod(default_args={'pool_asset': 'pool_token', 'a_asset': 'asset_a', 'b_asset': 'asset_b'})
    def burn(
        self,
        pool_xfer: algopy.gtxn.AssetTransferTransaction,
        pool_asset: algopy.Asset,
        a_asset: algopy.Asset,
        b_asset: algopy.Asset,
    ) -> None: ...

    @algopy.arc4.abimethod(default_args={'a_asset': 'asset_a', 'b_asset': 'asset_b'})
    def swap(
        self,
        swap_xfer: algopy.gtxn.AssetTransferTransaction,
        a_asset: algopy.Asset,
        b_asset: algopy.Asset,
    ) -> None: ...
