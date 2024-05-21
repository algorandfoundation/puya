# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Greeter(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_method_selector_kinds(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_method_overload(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_arg_conversion(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_15plus_args(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_void(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_ref_types(
        self,
        app: algopy.Application,
        asset: algopy.Asset,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_native_string(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_native_bytes(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_native_uint64(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_native_biguint(
        self,
        app: algopy.Application,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_native_tuple(
        self,
        app: algopy.Application,
    ) -> None: ...
