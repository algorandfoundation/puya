# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class ATuple(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class AStruct(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class TemplateVariablesContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def get_bytes(
        self,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def get_big_uint(
        self,
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod
    def get_a_named_tuple(
        self,
    ) -> ATuple: ...

    @algopy.arc4.abimethod
    def get_a_tuple(
        self,
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def get_a_struct(
        self,
    ) -> AStruct: ...
