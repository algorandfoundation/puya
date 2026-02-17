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

class NestedItemArrayUInt64(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def bootstrap(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def append(
        self,
        value: Parent,
    ) -> None: ...

    @algopy.arc4.abimethod
    def pop(
        self,
    ) -> Parent: ...

    @algopy.arc4.abimethod
    def nested_uint(
        self,
        idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def nested_bool(
        self,
        idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def nested_arr_append(
        self,
        item_idx: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def nested_arr_pop(
        self,
        item_idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def dynamic_append(
        self,
        item: ItemWithArray,
    ) -> None: ...

    @algopy.arc4.abimethod
    def dynamic_pop(
        self,
    ) -> ItemWithArray: ...

    @algopy.arc4.abimethod
    def clear_padding(
        self,
    ) -> None: ...
