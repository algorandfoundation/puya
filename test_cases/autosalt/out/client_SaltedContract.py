# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class SaltedContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def noop(
        self,
    ) -> None: ...
