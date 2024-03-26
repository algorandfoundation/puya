# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class StateProxyContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(allow_actions=['OptIn'], create='require')
    def create(
        self,
    ) -> None: ...
