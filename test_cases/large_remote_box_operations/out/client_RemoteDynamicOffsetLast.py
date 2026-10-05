# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class RemoteDynamicOffsetLast(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def bootstrap(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def concat(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        array: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def append(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def pop(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def verify(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        expected: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def get(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def set(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        idx: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
