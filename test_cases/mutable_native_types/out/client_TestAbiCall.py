# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class TestAbiCall(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_fixed_struct(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_nested_struct(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_dynamic_struct(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_fixed_array(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_native_array(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_log(
        self,
    ) -> None: ...
