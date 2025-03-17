# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ItxnNamedTuple(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def named_tuple_itxn(
        self,
        amt: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def named_tuple_itxn2(
        self,
        amt: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...
