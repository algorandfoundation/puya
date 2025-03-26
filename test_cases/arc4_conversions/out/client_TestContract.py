# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TestContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_literal_encoding(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_native_encoding(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_arc4_encoding(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_uint64_encoding(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_static_encoding(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_dynamic_encoding(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_bytes_to_fixed(
        self,
        wrong_size: algopy.arc4.Bool,
    ) -> None: ...
