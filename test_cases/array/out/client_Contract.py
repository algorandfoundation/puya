# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class Contract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def test_array(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_extend(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_multiple_append(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def overhead(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_too_long(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_copy_and_extend(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_evaluation_order(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_allocations(
        self,
        num: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_iteration(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_quicksort(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_unobserved_write(
        self,
    ) -> None: ...
