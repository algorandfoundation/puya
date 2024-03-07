# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy


class TransactionContract(puyapy.arc4.ARC4Client):
    @puyapy.arc4.abimethod(create=True)
    def create(
        self,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def pay(
        self,
        txn: puyapy.gtxn.PaymentTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def key(
        self,
        txn: puyapy.gtxn.KeyRegistrationTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def asset_config(
        self,
        txn: puyapy.gtxn.AssetConfigTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def asset_transfer(
        self,
        txn: puyapy.gtxn.AssetTransferTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def asset_freeze(
        self,
        txn: puyapy.gtxn.AssetFreezeTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def application_call(
        self,
        txn: puyapy.gtxn.ApplicationCallTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def multiple_txns(
        self,
        txn1: puyapy.gtxn.ApplicationCallTransaction,
        txn2: puyapy.gtxn.ApplicationCallTransaction,
        txn3: puyapy.gtxn.ApplicationCallTransaction,
    ) -> None:
        raise NotImplementedError

    @puyapy.arc4.abimethod
    def any_txn(
        self,
        _txn1: puyapy.gtxn.ApplicationCallTransaction,
        _txn2: puyapy.gtxn.ApplicationCallTransaction,
        _txn3: puyapy.gtxn.ApplicationCallTransaction,
    ) -> None:
        raise NotImplementedError
