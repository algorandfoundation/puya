# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class CustomApproval2(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def add_one(
        self,
        x: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
