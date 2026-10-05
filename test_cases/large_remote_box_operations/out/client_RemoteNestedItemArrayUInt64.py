# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class Child(algopy.arc4.Struct):
    uint: algopy.arc4.UIntN[typing.Literal[64]]
    bool_: algopy.arc4.Bool

class Parent(algopy.arc4.Struct):
    child: Child
    bar: algopy.arc4.UIntN[typing.Literal[64]]

class ItemWithArray(algopy.arc4.Struct):
    arr: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]

class RemoteNestedItemArrayUInt64(algopy.arc4.ARC4Client, typing.Protocol):
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
    def pop(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> Parent: ...

    @algopy.arc4.abimethod
    def nested_uint(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def nested_bool(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def nested_arr_append(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        item_idx: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def nested_arr_pop(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        item_idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def dynamic_append(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        item: ItemWithArray,
    ) -> None: ...

    @algopy.arc4.abimethod
    def dynamic_pop(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> ItemWithArray: ...

    @algopy.arc4.abimethod
    def clear_padding(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
