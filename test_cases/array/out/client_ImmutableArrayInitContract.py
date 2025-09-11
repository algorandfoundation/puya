# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ImmutableArrayInitContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_immutable_array_init(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_immutable_array_init_without_type_generic(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_reference_array_init(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_reference_array_init_without_type_generic(
        self,
    ) -> None: ...
