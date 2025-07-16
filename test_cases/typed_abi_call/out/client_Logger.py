# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class LogMessage(algopy.arc4.Struct):
    level: algopy.arc4.UIntN[typing.Literal[64]]
    message: algopy.arc4.String

class LogStruct(algopy.arc4.Struct):
    level: algopy.arc4.UIntN[typing.Literal[64]]
    message: algopy.arc4.String

class Logger(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def is_a_b(
        self,
        a: algopy.arc4.DynamicBytes,
        b: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod
    def echo(
        self,
        value: algopy.arc4.String,
    ) -> algopy.arc4.String: ...

    @algopy.arc4.abimethod
    def no_args(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def log(
        self,
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log2(
        self,
        value: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log3(
        self,
        value: algopy.arc4.String,
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log4(
        self,
        value: algopy.arc4.Bool,
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log5(
        self,
        value: algopy.arc4.DynamicBytes,
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log6(
        self,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        account: algopy.arc4.Address,
        app: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod(name='log')
    def log7(
        self,
        address: algopy.arc4.Address,
    ) -> None: ...

    @algopy.arc4.abimethod
    def echo_native_string(
        self,
        value: algopy.arc4.String,
    ) -> algopy.arc4.String: ...

    @algopy.arc4.abimethod
    def echo_native_bytes(
        self,
        value: algopy.arc4.DynamicBytes,
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def echo_native_uint64(
        self,
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def echo_native_biguint(
        self,
        value: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.BigUIntN[typing.Literal[512]]: ...

    @algopy.arc4.abimethod(resource_encoding='foreign_index')
    def echo_resource_by_foreign_index(
        self,
        asset: algopy.Asset,
        app: algopy.Application,
        acc: algopy.Account,
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Address]: ...

    @algopy.arc4.abimethod
    def echo_resource_by_value(
        self,
        asset: algopy.arc4.UIntN[typing.Literal[64]],
        app: algopy.arc4.UIntN[typing.Literal[64]],
        acc: algopy.arc4.Address,
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Address]: ...

    @algopy.arc4.abimethod
    def echo_native_tuple(
        self,
        s: algopy.arc4.String,
        b: algopy.arc4.DynamicBytes,
        u: algopy.arc4.UIntN[typing.Literal[64]],
        bu: algopy.arc4.BigUIntN[typing.Literal[512]],
    ) -> algopy.arc4.Tuple[algopy.arc4.String, algopy.arc4.DynamicBytes, algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.BigUIntN[typing.Literal[512]]]: ...

    @algopy.arc4.abimethod
    def echo_nested_tuple(
        self,
        tuple_of_tuples: algopy.arc4.Tuple[algopy.arc4.Tuple[algopy.arc4.String, algopy.arc4.String], algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.DynamicBytes]],
    ) -> algopy.arc4.Tuple[algopy.arc4.Tuple[algopy.arc4.String, algopy.arc4.String], algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.DynamicBytes]]: ...

    @algopy.arc4.abimethod
    def return_args_after_14th(
        self,
        _a1: algopy.arc4.UIntN[typing.Literal[64]],
        _a2: algopy.arc4.UIntN[typing.Literal[64]],
        _a3: algopy.arc4.UIntN[typing.Literal[64]],
        _a4: algopy.arc4.UIntN[typing.Literal[64]],
        _a5: algopy.arc4.UIntN[typing.Literal[64]],
        _a6: algopy.arc4.UIntN[typing.Literal[64]],
        _a7: algopy.arc4.UIntN[typing.Literal[64]],
        _a8: algopy.arc4.UIntN[typing.Literal[64]],
        _a9: algopy.arc4.UIntN[typing.Literal[64]],
        _a10: algopy.arc4.UIntN[typing.Literal[64]],
        _a11: algopy.arc4.UIntN[typing.Literal[64]],
        _a12: algopy.arc4.UIntN[typing.Literal[64]],
        _a13: algopy.arc4.UIntN[typing.Literal[64]],
        _a14: algopy.arc4.UIntN[typing.Literal[64]],
        a15: algopy.arc4.UIntN[typing.Literal[8]],
        a16: algopy.arc4.UIntN[typing.Literal[8]],
        a17: algopy.arc4.UIntN[typing.Literal[8]],
        a18: algopy.arc4.UIntN[typing.Literal[8]],
        a19: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[8]], algopy.arc4.UIntN[typing.Literal[8]], algopy.arc4.UIntN[typing.Literal[8]], algopy.arc4.UIntN[typing.Literal[8]]],
        a20: algopy.arc4.UIntN[typing.Literal[8]],
    ) -> algopy.arc4.DynamicBytes: ...

    @algopy.arc4.abimethod
    def logs_are_equal(
        self,
        log_1: LogMessage,
        log_2: LogMessage,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def echo_log_struct(
        self,
        log: LogStruct,
    ) -> LogStruct: ...
