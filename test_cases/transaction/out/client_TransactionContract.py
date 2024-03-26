# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TransactionContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(create=True)
    def create(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def pay(
        self,
        txn: algopy.gtxn.PaymentTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def key(
        self,
        txn: algopy.gtxn.KeyRegistrationTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def asset_config(
        self,
        txn: algopy.gtxn.AssetConfigTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def asset_transfer(
        self,
        txn: algopy.gtxn.AssetTransferTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def asset_freeze(
        self,
        txn: algopy.gtxn.AssetFreezeTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def application_call(
        self,
        txn: algopy.gtxn.ApplicationCallTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def multiple_txns(
        self,
        txn1: algopy.gtxn.ApplicationCallTransaction,
        txn2: algopy.gtxn.ApplicationCallTransaction,
        txn3: algopy.gtxn.ApplicationCallTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def any_txn(
        self,
        txn1: algopy.gtxn.Transaction,
        txn2: algopy.gtxn.Transaction,
        txn3: algopy.gtxn.Transaction,
    ) -> None: ...
