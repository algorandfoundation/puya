# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Arc4DynamicStringArrayContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def xyz(
        self,
    ) -> algopy.arc4.DynamicArray[algopy.arc4.String]: ...

    @algopy.arc4.abimethod
    def xyz_raw(
        self,
    ) -> algopy.arc4.DynamicArray[algopy.arc4.String]: ...
