# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class NestedTuplesStorage(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(allow_actions=['OptIn'])
    def bootstrap(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def mutate_tuple(
        self,
        val: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def mutate_box(
        self,
        val: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def mutate_global(
        self,
        val: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def mutate_local(
        self,
        val: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
