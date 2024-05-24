# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TestContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(create='require')
    def create(
        self,
        bool_param: algopy.arc4.Bool,
        uint64_param: algopy.arc4.UIntN[typing.Literal[64]],
        bytes_param: algopy.arc4.DynamicBytes,
        biguint_param: algopy.arc4.BigUIntN[typing.Literal[512]],
        string_param: algopy.arc4.String,
        tuple_param: algopy.arc4.Tuple[algopy.arc4.Bool, algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.DynamicBytes, algopy.arc4.BigUIntN[typing.Literal[512]], algopy.arc4.String],
    ) -> algopy.arc4.Tuple[algopy.arc4.Bool, algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.DynamicBytes, algopy.arc4.BigUIntN[typing.Literal[512]], algopy.arc4.String]: ...

    @algopy.arc4.abimethod
    def tuple_of_arc4(
        self,
        args: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[8]], algopy.arc4.Address],
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[8]], algopy.arc4.Address]: ...
