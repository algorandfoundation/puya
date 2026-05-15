# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class BoxReadBoxLenExistenceCheck(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def len_via_value(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...
