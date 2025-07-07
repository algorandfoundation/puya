# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class Payment(algopy.arc4.Struct):
    receiver: algopy.arc4.Address
    asset: algopy.arc4.UIntN[typing.Literal[64]]
    amt: algopy.arc4.UIntN[typing.Literal[64]]

class FixedStruct(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class NamedTup(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def fixed_initialize(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def add_payment(
        self,
        pay: Payment,
    ) -> None: ...

    @algopy.arc4.abimethod
    def increment_payment(
        self,
        index: algopy.arc4.UIntN[typing.Literal[64]],
        amt: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def create_storage(
        self,
        box_key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def local_struct(
        self,
    ) -> Payment: ...

    @algopy.arc4.abimethod
    def delete_storage(
        self,
        box_key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def struct_arg(
        self,
        box_key: algopy.arc4.UIntN[typing.Literal[64]],
        a: FixedStruct,
    ) -> None: ...

    @algopy.arc4.abimethod
    def struct_return(
        self,
    ) -> FixedStruct: ...

    @algopy.arc4.abimethod
    def tup_return(
        self,
    ) -> NamedTup: ...

    @algopy.arc4.abimethod
    def calculate_sum(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def test_arr(
        self,
        arr: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]]: ...
