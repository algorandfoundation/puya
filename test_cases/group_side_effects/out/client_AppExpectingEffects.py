# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class AppExpectingEffects(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def create_group(
        self,
        asset_create: algopy.gtxn.AssetConfigTransaction,
        app_create: algopy.gtxn.ApplicationCallTransaction,
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def log_group(
        self,
        app_call: algopy.gtxn.ApplicationCallTransaction,
    ) -> None: ...
