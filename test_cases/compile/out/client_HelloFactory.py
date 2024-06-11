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
    def test_compile_contract(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_compile_contract_tmpl(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_compile_contract_prfx(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_compile_contract_large(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_arc4_create(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_arc4_create_tmpl(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_arc4_create_prfx(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_arc4_create_large(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_arc4_update(
        self,
    ) -> None: ...
