# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class DynamicITxnGroup(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_firstly(
        self,
        addresses: algopy.arc4.DynamicArray[algopy.arc4.Address],
        funds: algopy.gtxn.PaymentTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_looply(
        self,
        addresses: algopy.arc4.DynamicArray[algopy.arc4.Address],
        funds: algopy.gtxn.PaymentTransaction,
    ) -> None: ...
