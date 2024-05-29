# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class DynamicArrayContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_static_elements(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_dynamic_elements(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_mixed_single_dynamic_elements(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_mixed_multiple_dynamic_elements(
        self,
    ) -> None: ...
