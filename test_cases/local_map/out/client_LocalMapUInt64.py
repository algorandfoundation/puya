# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class LocalMapUInt64(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(allow_actions=['OptIn'], create='require')
    def create(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def get(
        self,
        account: algopy.arc4.Address,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def get_with_default(
        self,
        account: algopy.arc4.Address,
        key: algopy.arc4.UIntN[typing.Literal[64]],
        default: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def set(
        self,
        account: algopy.arc4.Address,
        key: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def delete(
        self,
        account: algopy.arc4.Address,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def in_(
        self,
        account: algopy.arc4.Address,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def prefix(
        self,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def maybe(
        self,
        account: algopy.arc4.Address,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Bool]: ...

    @algopy.arc4.abimethod
    def get_via_state(
        self,
        account: algopy.arc4.Address,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
