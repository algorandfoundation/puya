# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class FixedBytesABI(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_itxn_validate_caller_bytes(
        self,
        val: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_itxn_validate_callee_manual(
        self,
        val: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_itxn_validate_callee_router(
        self,
        val: algopy.arc4.DynamicBytes,
    ) -> None: ...
