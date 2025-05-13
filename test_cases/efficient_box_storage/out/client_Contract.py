# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def create_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def update_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def append(
        self,
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def box_len(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def box_exists_len(
        self,
    ) -> algopy.arc4.Tuple[algopy.arc4.Bool, algopy.arc4.UIntN[typing.Literal[64]]]: ...
