# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class ImmutableArrayContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_uint64_array(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_bool_array(
        self,
        length: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_fixed_size_tuple_array(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_fixed_size_named_tuple_array(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_dynamic_sized_tuple_array(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_dynamic_sized_named_tuple_array(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_bit_packed_tuples(
        self,
    ) -> None: ...
