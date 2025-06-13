# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class FixedStruct(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class NestedStruct(algopy.arc4.Struct):
    fixed: FixedStruct
    c: algopy.arc4.UIntN[typing.Literal[64]]

class DynamicStruct(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    b: algopy.arc4.UIntN[typing.Literal[64]]
    c: algopy.arc4.DynamicBytes
    d: algopy.arc4.String
    e: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]]

class CallMe(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(allow_actions=['DeleteApplication'])
    def delete(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def fixed_struct_arg(
        self,
        arg: FixedStruct,
    ) -> None: ...

    @algopy.arc4.abimethod
    def fixed_struct_ret(
        self,
    ) -> FixedStruct: ...

    @algopy.arc4.abimethod
    def nested_struct_arg(
        self,
        arg: NestedStruct,
    ) -> None: ...

    @algopy.arc4.abimethod
    def nested_struct_ret(
        self,
    ) -> NestedStruct: ...

    @algopy.arc4.abimethod
    def dynamic_struct_arg(
        self,
        arg: DynamicStruct,
    ) -> None: ...

    @algopy.arc4.abimethod
    def dynamic_struct_ret(
        self,
    ) -> DynamicStruct: ...

    @algopy.arc4.abimethod
    def fixed_arr_arg(
        self,
        arg: algopy.arc4.StaticArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]], typing.Literal[3]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def fixed_arr_ret(
        self,
    ) -> algopy.arc4.StaticArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]], typing.Literal[3]]: ...

    @algopy.arc4.abimethod
    def native_arr_arg(
        self,
        arg: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def native_arr_ret(
        self,
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]]: ...

    @algopy.arc4.abimethod
    def log_it(
        self,
    ) -> None: ...
