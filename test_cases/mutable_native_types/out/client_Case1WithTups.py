# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class NamedTup(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class Case1WithTups(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def create_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def num_tups(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def add_tup(
        self,
        tup: NamedTup,
    ) -> None: ...

    @algopy.arc4.abimethod
    def get_tup(
        self,
        index: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> NamedTup: ...

    @algopy.arc4.abimethod
    def sum(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def add_many_tups(
        self,
        tups: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def add_fixed_tups(
        self,
        tups: algopy.arc4.StaticArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]], typing.Literal[3]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def set_a(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def set_b(
        self,
        b: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def get_3_tups(
        self,
        start: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.StaticArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]], typing.Literal[3]]: ...
