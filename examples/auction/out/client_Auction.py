# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Auction(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def opt_into_asset(
        self,
        asset: algopy.Asset,
    ) -> None: ...

    @algopy.arc4.abimethod
    def start_auction(
        self,
        starting_price: algopy.arc4.UIntN[typing.Literal[64]],
        length: algopy.arc4.UIntN[typing.Literal[64]],
        axfer: algopy.gtxn.AssetTransferTransaction,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod(allow_actions=['OptIn'])
    def opt_in(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def bid(
        self,
        pay: algopy.gtxn.PaymentTransaction,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def claim_bids(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def claim_asset(
        self,
        asset: algopy.Asset,
    ) -> None: ...

    @algopy.arc4.abimethod(allow_actions=['DeleteApplication'])
    def delete_application(
        self,
    ) -> None: ...
