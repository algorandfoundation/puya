# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ArrayUInt64(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def bootstrap(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def append(
        self,
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def concat(
        self,
        array: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def pop(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def get(
        self,
        idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def set(
        self,
        idx: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def verify(
        self,
        expected: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...
