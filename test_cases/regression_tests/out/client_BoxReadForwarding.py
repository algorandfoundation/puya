# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class BoxReadForwarding(algopy.arc4.ARC4Client, typing.Protocol):
    """

        A value read from a box must not observe later modifications to that box.
        Cases restore any box they modify that a later case reads.
    
    """
    @algopy.arc4.abimethod
    def run_all(
        self,
    ) -> None: ...
