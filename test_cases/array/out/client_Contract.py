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
    def overhead(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_array_too_long(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_quicksort(
        self,
    ) -> None: ...
