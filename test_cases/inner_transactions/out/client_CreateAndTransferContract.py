# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class CreateAndTransferContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def create_and_transfer(
        self,
    ) -> None: ...
