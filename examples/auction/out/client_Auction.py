# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class Auction(puyapy.arc4.ARC4Client):
    @puyapy.arc4.abimethod
    def opt_into_asset(
        self,
        asset: puyapy.Asset,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def start_auction(
        self,
        starting_price: puyapy.arc4.UInt64,
        length: puyapy.arc4.UInt64,
        axfer: puyapy.gtxn.AssetTransferTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def opt_in(
        self,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def bid(
        self,
        pay: puyapy.gtxn.PaymentTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def claim_bids(
        self,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def claim_asset(
        self,
        asset: puyapy.Asset,
    ) -> None:
        raise NotImplementedError
