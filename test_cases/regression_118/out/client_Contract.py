# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def verify(
        self,
        values: algopy.arc4.DynamicArray[algopy.arc4.BigUIntN[typing.Literal[256]]],
    ) -> algopy.arc4.Tuple[algopy.arc4.Bool, algopy.arc4.String]: ...
