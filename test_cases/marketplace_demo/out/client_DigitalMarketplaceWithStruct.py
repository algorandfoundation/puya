# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class DigitalMarketplaceWithStruct(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(readonly=True)
    def getListingsMbr(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def allowAsset(
        self,
        mbr_pay: algopy.gtxn.PaymentTransaction,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def firstDeposit(
        self,
        mbr_pay: algopy.gtxn.PaymentTransaction,
        xfer: algopy.gtxn.AssetTransferTransaction,
        unitary_price: algopy.arc4.UIntN[typing.Literal[64]],
        nonce: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def deposit(
        self,
        xfer: algopy.gtxn.AssetTransferTransaction,
        nonce: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def setPrice(
        self,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        nonce: algopy.arc4.UIntN[typing.Literal[64]],
        unitary_price: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def buy(
        self,
        owner: algopy.arc4.Address,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        nonce: algopy.arc4.UIntN[typing.Literal[64]],
        buy_pay: algopy.gtxn.PaymentTransaction,
        quantity: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def withdraw(
        self,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        nonce: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def bid(
        self,
        owner: algopy.arc4.Address,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        nonce: algopy.arc4.UIntN[typing.Literal[64]],
        bid_pay: algopy.gtxn.PaymentTransaction,
        quantity: algopy.arc4.UIntN[typing.Literal[64]],
        unitary_price: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def acceptBid(
        self,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        nonce: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
