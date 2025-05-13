# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class NamedTup(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class FixedWithTups(algopy.arc4.ARC4Client, typing.Protocol):
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
