# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TemplateVariablesContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def get_bytes(
        self,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def get_big_uint(
        self,
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...
