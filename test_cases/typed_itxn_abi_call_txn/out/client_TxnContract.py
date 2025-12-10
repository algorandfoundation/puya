# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TxnContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def call_with_txn(
        self,
        a: algopy.arc4.DynamicBytes,
        acfg: algopy.gtxn.Transaction,
        b: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def call_with_acfg(
        self,
        a: algopy.arc4.DynamicBytes,
        acfg: algopy.gtxn.AssetConfigTransaction,
        b: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def call_with_acfg_no_return(
        self,
        a: algopy.arc4.DynamicBytes,
        acfg: algopy.gtxn.AssetConfigTransaction,
        b: algopy.arc4.DynamicBytes,
    ) -> None: ...
