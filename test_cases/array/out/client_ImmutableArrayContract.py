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
    def test_biguint_array(
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
    def test_implicit_conversion_log(
        self,
        arr: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_implicit_conversion_emit(
        self,
        arr: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> None: ...

    @algopy.arc4.abimethod
    def test_nested_array(
        self,
        arr_to_add: algopy.arc4.UIntN[typing.Literal[64]],
        arr: algopy.arc4.DynamicArray[algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def test_bit_packed_tuples(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod
    def sum_uints_and_lengths_and_trues(
        self,
        arr1: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]],
        arr2: algopy.arc4.DynamicArray[algopy.arc4.Bool],
        arr3: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Bool, algopy.arc4.Bool]],
        arr4: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.String]],
    ) -> algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def test_uint64_return(
        self,
        append: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def test_bool_return(
        self,
        append: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Bool]: ...

    @algopy.arc4.abimethod
    def test_tuple_return(
        self,
        append: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Bool, algopy.arc4.Bool]]: ...

    @algopy.arc4.abimethod
    def test_dynamic_tuple_return(
        self,
        append: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.String]]: ...

    @algopy.arc4.abimethod
    def test_convert_to_array_and_back(
        self,
        arr: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Bool, algopy.arc4.Bool]],
        append: algopy.arc4.UIntN[typing.Literal[64]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.Bool, algopy.arc4.Bool]]: ...

    @algopy.arc4.abimethod
    def test_concat_with_arc4_tuple(
        self,
        arg: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def test_concat_with_native_tuple(
        self,
        arg: algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.UIntN[typing.Literal[64]]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[64]]]: ...

    @algopy.arc4.abimethod
    def test_dynamic_concat_with_arc4_tuple(
        self,
        arg: algopy.arc4.Tuple[algopy.arc4.String, algopy.arc4.String],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.String]: ...

    @algopy.arc4.abimethod
    def test_dynamic_concat_with_native_tuple(
        self,
        arg: algopy.arc4.Tuple[algopy.arc4.String, algopy.arc4.String],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.String]: ...

    @algopy.arc4.abimethod
    def test_concat_immutable_dynamic(
        self,
        imm1: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.String]],
        imm2: algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.String]],
    ) -> algopy.arc4.DynamicArray[algopy.arc4.Tuple[algopy.arc4.UIntN[typing.Literal[64]], algopy.arc4.String]]: ...
