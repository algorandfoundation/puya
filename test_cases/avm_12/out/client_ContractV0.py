# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ContractV0(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(allow_actions=['UpdateApplication'])
    def update(
        self,
    ) -> None: ...
