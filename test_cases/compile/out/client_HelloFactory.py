# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class HelloFactory(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_logicsig(
        self,
    ) -> algopy.arc4.Address: ...

    @algopy.arc4.abimethod
    def test_get_program(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_get_program_tmpl(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_get_program_prfx(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_get_program_large(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_abi_call(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_abi_call_tmpl(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_abi_call_prfx(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_abi_call_large(
        self,
    ) -> None: ...
