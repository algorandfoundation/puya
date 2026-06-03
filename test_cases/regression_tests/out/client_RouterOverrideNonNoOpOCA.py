# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class RouterOverrideNonNoOpOCA(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def noop_method(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def another_noop_method(
        self,
        val: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod(allow_actions=['UpdateApplication'])
    def update_application(
        self,
    ) -> None: ...
