# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ConstantProductAMM(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def set_governor(
        self,
        new_governor: algopy.arc4.Address,
    ) -> None:
        """
        sets the governor of the contract, may only be called by the current governor
        """

    @algopy.arc4.abimethod(resource_encoding='foreign_index')
    def bootstrap(
        self,
        seed: algopy.gtxn.PaymentTransaction,
        a_asset: algopy.Asset,
        b_asset: algopy.Asset,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]:
        """
        bootstraps the contract by opting into the assets and creating the pool token.
        Note this method will fail if it is attempted more than once on the same contract since the assets and pool token application state values are marked as static and cannot be overridden.
        """

    @algopy.arc4.abimethod(resource_encoding='foreign_index')
    def mint(
        self,
        a_xfer: algopy.gtxn.AssetTransferTransaction,
        b_xfer: algopy.gtxn.AssetTransferTransaction,
        pool_asset: algopy.Asset,
        a_asset: algopy.Asset,
        b_asset: algopy.Asset,
    ) -> None:
        """
        mint pool tokens given some amount of asset A and asset B.
        Given some amount of Asset A and Asset B in the transfers, mint some number of pool tokens commensurate with the pools current balance and circulating supply of pool tokens.
        """

    @algopy.arc4.abimethod(resource_encoding='foreign_index')
    def burn(
        self,
        pool_xfer: algopy.gtxn.AssetTransferTransaction,
        pool_asset: algopy.Asset,
        a_asset: algopy.Asset,
        b_asset: algopy.Asset,
    ) -> None:
        """
        burn pool tokens to get back some amount of asset A and asset B
        """

    @algopy.arc4.abimethod(resource_encoding='foreign_index')
    def swap(
        self,
        swap_xfer: algopy.gtxn.AssetTransferTransaction,
        a_asset: algopy.Asset,
        b_asset: algopy.Asset,
    ) -> None:
        """
        Swap some amount of either asset A or asset B for the other
        """
