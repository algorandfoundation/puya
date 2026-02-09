// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class ImmutableArrayContract extends Contract {

    @abimethod
    test_uint64_array(

    ): void {
        err("stub only")
    }

    @abimethod
    test_biguint_array(

    ): void {
        err("stub only")
    }

    @abimethod
    test_bool_array(
        length: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    test_fixed_size_tuple_array(

    ): void {
        err("stub only")
    }

    @abimethod
    test_fixed_size_named_tuple_array(

    ): void {
        err("stub only")
    }

    @abimethod
    test_dynamic_sized_tuple_array(

    ): void {
        err("stub only")
    }

    @abimethod
    test_dynamic_sized_named_tuple_array(

    ): void {
        err("stub only")
    }

    @abimethod
    test_implicit_conversion_log(
        arr: arc4.DynamicArray<arc4.Uint<64>>,
    ): void {
        err("stub only")
    }

    @abimethod
    test_implicit_conversion_emit(
        arr: arc4.DynamicArray<arc4.Uint<64>>,
    ): void {
        err("stub only")
    }

    @abimethod
    test_nested_array(
        arr_to_add: arc4.Uint<64>,
        arr: arc4.DynamicArray<arc4.DynamicArray<arc4.Uint<64>>>,
    ): arc4.DynamicArray<arc4.Uint<64>> {
        err("stub only")
    }

    @abimethod
    test_bit_packed_tuples(

    ): void {
        err("stub only")
    }

    @abimethod
    sum_uints_and_lengths_and_trues(
        arr1: arc4.DynamicArray<arc4.Uint<64>>,
        arr2: arc4.DynamicArray<arc4.Bool>,
        arr3: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Bool, arc4.Bool]>>,
        arr4: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Str]>>,
    ): arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>, arc4.Uint<64>, arc4.Uint<64>]> {
        err("stub only")
    }

    @abimethod
    test_uint64_return(
        append: arc4.Uint<64>,
    ): arc4.DynamicArray<arc4.Uint<64>> {
        err("stub only")
    }

    @abimethod
    test_bool_return(
        append: arc4.Uint<64>,
    ): arc4.DynamicArray<arc4.Bool> {
        err("stub only")
    }

    @abimethod
    test_tuple_return(
        append: arc4.Uint<64>,
    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Bool, arc4.Bool]>> {
        err("stub only")
    }

    @abimethod
    test_dynamic_tuple_return(
        append: arc4.Uint<64>,
    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Str]>> {
        err("stub only")
    }

    @abimethod
    test_convert_to_array_and_back(
        arr: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Bool, arc4.Bool]>>,
        append: arc4.Uint<64>,
    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Bool, arc4.Bool]>> {
        err("stub only")
    }

    @abimethod
    test_concat_with_arc4_tuple(
        arg: arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>,
    ): arc4.DynamicArray<arc4.Uint<64>> {
        err("stub only")
    }

    @abimethod
    test_concat_with_native_tuple(
        arg: arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>,
    ): arc4.DynamicArray<arc4.Uint<64>> {
        err("stub only")
    }

    @abimethod
    test_dynamic_concat_with_arc4_tuple(
        arg: arc4.Tuple<readonly [arc4.Str, arc4.Str]>,
    ): arc4.DynamicArray<arc4.Str> {
        err("stub only")
    }

    @abimethod
    test_dynamic_concat_with_native_tuple(
        arg: arc4.Tuple<readonly [arc4.Str, arc4.Str]>,
    ): arc4.DynamicArray<arc4.Str> {
        err("stub only")
    }

    @abimethod
    test_concat_immutable_dynamic(
        imm1: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Str]>>,
        imm2: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Str]>>,
    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Str]>> {
        err("stub only")
    }

    @abimethod
    test_immutable_arc4(
        imm: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>>,
    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>> {
        err("stub only")
    }

    @abimethod
    test_imm_fixed_arr(

    ): FixedArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>, 3> {
        err("stub only")
    }
}
