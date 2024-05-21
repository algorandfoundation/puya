# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy


class BoxContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def set_boxes(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.DynamicBytes,
        c: algopy.arc4.String,
    ) -> None: ...

    @algopy.arc4.abimethod
    def read_boxes(
        self,
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.DynamicBytes, algopy.arc4.String]: ...

    @algopy.arc4.abimethod
    def boxes_exist(
        self,
    ) -> algopy.arc4.Tuple[algopy.arc4.Bool, algopy.arc4.Bool, algopy.arc4.Bool]: ...

    @algopy.arc4.abimethod
    def slice_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def arc4_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def box_blob(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def box_map_test(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def box_map_set(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.String,
    ) -> None: ...

    @algopy.arc4.abimethod
    def box_map_get(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.String: ...

    @algopy.arc4.abimethod
    def box_map_exists(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...
