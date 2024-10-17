# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class TestTuple(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.BigUIntN[typing.Literal[512]]
    c: algopy.arc4.String
    d: algopy.arc4.DynamicBytes

class NamedTuplesContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def build_tuple(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.BigUIntN[typing.Literal[512]],
        c: algopy.arc4.String,
        d: algopy.arc4.DynamicBytes,
    ) -> TestTuple: ...

    @algopy.arc4.abimethod
    def test_tuple(
        self,
        value: TestTuple,
    ) -> None: ...
