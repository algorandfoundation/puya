# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class InnerStruct(algopy.arc4.Struct):
    c: algopy.arc4.UIntN[typing.Literal[64]]
    arr_arr: algopy.arc4.DynamicArray[algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]]
    d: algopy.arc4.UIntN[typing.Literal[64]]

class NestedStruct(algopy.arc4.Struct):
    a: algopy.arc4.UIntN[typing.Literal[64]]
    inner: InnerStruct
    woah: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.DynamicArray[algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]], algopy.arc4.UIntN[typing.Literal[64]]]]
    b: algopy.arc4.UIntN[typing.Literal[64]]

class BoxContract(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod
    def set_boxes(
        self,
        a: algopy.arc4.UIntN[typing.Literal[64]],
        b: algopy.arc4.DynamicBytes,
        c: algopy.arc4.String,
    ) -> None: ...

    @algopy.arc4.abimethod
    def check_keys(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def create_many_ints(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def set_many_ints(
        self,
        index: algopy.arc4.UIntN[typing.Literal[64]],
        value: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def sum_many_ints(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def delete_boxes(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def indirect_extract_and_replace(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def read_boxes(
        self,
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.DynamicBytes, algopy.arc4.String, algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def boxes_exist(
        self,
    ) -> algopy.arc4.Tuple[algopy.arc4.Bool, algopy.arc4.Bool, algopy.arc4.Bool, algopy.arc4.Bool]: ...

    @algopy.arc4.abimethod
    def create_dynamic_arr_struct(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def delete_dynamic_arr_struct(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def append_dynamic_arr_struct(
        self,
        times: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def pop_dynamic_arr_struct(
        self,
        times: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def set_nested_struct(
        self,
        struct: NestedStruct,
    ) -> None: ...

    @algopy.arc4.abimethod
    def nested_read(
        self,
        i1: algopy.arc4.UIntN[typing.Literal[64]],
        i2: algopy.arc4.UIntN[typing.Literal[64]],
        i3: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def sum_dynamic_arr_struct(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def create_dynamic_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def delete_dynamic_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def append_dynamic_box(
        self,
        times: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def pop_dynamic_box(
        self,
        times: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def sum_dynamic_box(
        self,
    ) -> algopy.arc4.UIntN[typing.Literal[64]]: ...

    @algopy.arc4.abimethod
    def slice_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def arc4_box(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_box_ref(
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
    def box_map_del(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def box_map_exists(
        self,
        key: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.Bool: ...
