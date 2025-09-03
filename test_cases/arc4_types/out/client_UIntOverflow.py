# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class UIntOverflow(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_uint8(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_uint16(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_uint32(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_as_uint64(
        self,
    ) -> None: ...
