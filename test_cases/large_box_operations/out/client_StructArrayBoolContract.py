# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class StructArrayBoolContract(algopy.arc4.ARC4Client, typing.Protocol):
    """
    Dynamic arrays of bool are bit packed, so in-place box operations must
        work in bits rather than bytes, and only update trailing head offsets by the
        number of bytes actually added or removed.

        The bool members either side of the array are not packed with each other (the
        array's head pointer sits between them), so each occupies its own byte and must
        be left undisturbed as the array is resized.
    """
    @algopy.arc4.abimethod
    def bootstrap(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def append(
        self,
        value: algopy.arc4.Bool,
    ) -> None: ...

    @algopy.arc4.abimethod
    def concat(
        self,
        array: algopy.arc4.DynamicArray[algopy.arc4.Bool],
    ) -> None: ...

    @algopy.arc4.abimethod
    def pop(
        self,
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def get(
        self,
        idx: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...

    @algopy.arc4.abimethod
    def set(
        self,
        idx: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.Bool,
    ) -> None: ...

    @algopy.arc4.abimethod
    def verify(
        self,
        expected: algopy.arc4.DynamicArray[algopy.arc4.Bool],
    ) -> None: ...
