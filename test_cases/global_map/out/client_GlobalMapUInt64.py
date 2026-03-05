# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class GlobalMapUInt64(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def get(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def get_with_default(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
        default: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def set(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def delete(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def in_(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def prefix(
        self,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def maybe(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Bool]: ...

    @algopy.arc4.abimethod
    def get_via_state(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
