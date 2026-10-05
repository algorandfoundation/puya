# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class Child(algopy.arc4.Struct):
    foo: algopy.arc4.UIntN[typing.Literal[64]]
    bar: algopy.arc4.UIntN[typing.Literal[64]]

class Parent(algopy.arc4.Struct):
    baz: algopy.arc4.UIntN[typing.Literal[64]]
    simple: Child
    buz: algopy.arc4.UIntN[typing.Literal[64]]

class RemoteNestedArrayUInt64(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def bootstrap(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def append(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        value: Parent,
    ) -> None: ...

    @algopy.arc4.abimethod
    def concat(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        array: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]], algopy.arc4.UIntN[typing.Literal[64]]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def pop(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> Parent: ...

    @algopy.arc4.abimethod
    def get(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> Parent: ...

    @algopy.arc4.abimethod
    def set(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        idx: algopy.arc4.UIntN[typing.Literal[64]],
        value: Parent,
    ) -> None: ...

    @algopy.arc4.abimethod
    def verify(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        expected: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]], algopy.arc4.UIntN[typing.Literal[64]]]],
    ) -> None: ...
