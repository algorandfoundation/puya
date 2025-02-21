# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class VRFVerifier(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def verify(
        self,
        message: algopy.arc4.DynamicBytes,
        proof: algopy.arc4.DynamicBytes,
        pk: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.Tuple[algopy.arc4.DynamicBytes, algopy.arc4.Bool]: ...
