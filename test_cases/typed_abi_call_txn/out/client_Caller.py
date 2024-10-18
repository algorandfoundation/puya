# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Caller(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_call_with_txn(
        self,
        a: algopy.arc4.DynamicBytes,
        b: algopy.arc4.DynamicBytes,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_call_with_acfg(
        self,
        a: algopy.arc4.DynamicBytes,
        b: algopy.arc4.DynamicBytes,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_call_with_infer(
        self,
        a: algopy.arc4.DynamicBytes,
        b: algopy.arc4.DynamicBytes,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_call_with_acfg_no_return(
        self,
        a: algopy.arc4.DynamicBytes,
        b: algopy.arc4.DynamicBytes,
        app: algopy.Application,
    ) -> None: ...
