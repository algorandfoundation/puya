# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class CheckApp(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(allow_actions=['DeleteApplication'])
    def delete_application(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_uint64(
        self,
        value: algopy.arc4.UIntN[typing.Literal[64]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_dynamic_bytes(
        self,
        value: algopy.arc4.DynamicBytes,
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_string(
        self,
        value: algopy.arc4.String,
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_biguint(
        self,
        value: algopy.arc4.BigUIntN[typing.Literal[512]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_bool(
        self,
        value: algopy.arc4.Bool,
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_dyn_array_uin64(
        self,
        value: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_static_array_uin64_3(
        self,
        value: algopy.arc4.StaticArray[algopy.arc4.UIntN[typing.Literal[64]], typing.Literal[3]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_dyn_array_struct(
        self,
        value: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Address]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_static_array_struct(
        self,
        value: algopy.arc4.StaticArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Address], typing.Literal[3]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_dyn_array_dyn_struct(
        self,
        value: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Address, algopy.arc4.DynamicBytes]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_static_array_dyn_struct(
        self,
        value: algopy.arc4.StaticArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Address, algopy.arc4.DynamicBytes], typing.Literal[3]],
        expected: algopy.arc4.DynamicBytes,
    ) -> None: ...
