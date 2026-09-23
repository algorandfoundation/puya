# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class RemoteBoxContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def local_app_is_current_app(
        self,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def explicit_location(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def read(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def read_with_default(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def maybe(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Bool]: ...

    @algopy.arc4.abimethod
    def exists(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def length(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def write(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def delete(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def create_and_splice(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def struct_member_write(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def big_read(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        index: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def big_write(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
        index: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def key_and_app(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Tuple[algopy.arc4.DynamicBytes, algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def passed_around(
        self,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
