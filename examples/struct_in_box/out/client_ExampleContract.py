# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class UserStruct(algopy.arc4.Struct):
    name: algopy.arc4.String
    id: algopy.arc4.UIntN[typing.Literal[64]]
    asset: algopy.arc4.UIntN[typing.Literal[64]]

class ExampleContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def add_user(
        self,
        user: UserStruct,
    ) -> None: ...

    @algopy.arc4.abimethod
    def attach_asset_to_user(
        self,
        user_id: algopy.arc4.UIntN[typing.Literal[64]],
        asset: algopy.Asset,
    ) -> None: ...

    @algopy.arc4.abimethod
    def get_user(
        self,
        user_id: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> UserStruct: ...
