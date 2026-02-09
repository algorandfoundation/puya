// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class InnerStruct extends arc4.Struct<{
    c: arc4.Uint<64>,
    arr_arr: arc4.DynamicArray<arc4.DynamicArray<arc4.Uint<64>>>,
    d: arc4.Uint<64>,
}> { }

export class NestedStruct extends arc4.Struct<{
    a: arc4.Uint<64>,
    inner: InnerStruct,
    woah: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.DynamicArray<arc4.DynamicArray<arc4.Uint<64>>>, arc4.Uint<64>]>>,
    b: arc4.Uint<64>,
}> { }

export abstract class BoxContract extends Contract {

    @abimethod
    set_boxes(
        a: arc4.Uint<64>,
        b: arc4.DynamicBytes,
        c: arc4.Str,
    ): void {
        err("stub only")
    }

    @abimethod
    check_keys(

    ): void {
        err("stub only")
    }

    @abimethod
    create_many_ints(

    ): void {
        err("stub only")
    }

    @abimethod
    set_many_ints(
        index: arc4.Uint<64>,
        value: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    create_big_fixed_bytes(

    ): void {
        err("stub only")
    }

    @abimethod
    update_big_fixed_bytes(
        start_index: arc4.Uint<64>,
        value: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    assert_big_fixed_bytes(
        index: arc4.Uint<64>,
        value: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    slice_big_fixed_bytes(
        start: arc4.Uint<64>,
        end: arc4.Uint<64>,
    ): arc4.DynamicBytes {
        err("stub only")
    }

    @abimethod
    create_big_bytes(
        size: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    update_big_bytes(
        start_index: arc4.Uint<64>,
        value: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    assert_big_bytes(
        index: arc4.Uint<64>,
        value: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod
    slice_big_bytes(
        start: arc4.Uint<64>,
        end: arc4.Uint<64>,
    ): arc4.DynamicBytes {
        err("stub only")
    }

    @abimethod
    sum_many_ints(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    delete_boxes(

    ): void {
        err("stub only")
    }

    @abimethod
    indirect_extract_and_replace(

    ): void {
        err("stub only")
    }

    @abimethod
    read_boxes(

    ): arc4.Tuple<readonly [arc4.Uint<64>, arc4.DynamicBytes, arc4.Str, arc4.Uint<64>]> {
        err("stub only")
    }

    @abimethod
    boxes_exist(

    ): arc4.Tuple<readonly [arc4.Bool, arc4.Bool, arc4.Bool, arc4.Bool]> {
        err("stub only")
    }

    @abimethod
    create_dynamic_arr_struct(

    ): void {
        err("stub only")
    }

    @abimethod
    delete_dynamic_arr_struct(

    ): void {
        err("stub only")
    }

    @abimethod
    append_dynamic_arr_struct(
        times: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    pop_dynamic_arr_struct(
        times: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    set_nested_struct(
        struct: NestedStruct,
    ): void {
        err("stub only")
    }

    @abimethod
    nested_write(
        index: arc4.Uint<64>,
        value: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    nested_read(
        i1: arc4.Uint<64>,
        i2: arc4.Uint<64>,
        i3: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    sum_dynamic_arr_struct(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    create_bools(

    ): void {
        err("stub only")
    }

    @abimethod
    set_bool(
        index: arc4.Uint<64>,
        value: arc4.Bool,
    ): void {
        err("stub only")
    }

    @abimethod
    sum_bools(
        stop_at_total: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    create_dynamic_box(

    ): void {
        err("stub only")
    }

    @abimethod
    delete_dynamic_box(

    ): void {
        err("stub only")
    }

    @abimethod
    append_dynamic_box(
        times: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    pop_dynamic_box(
        times: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    sum_dynamic_box(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    write_dynamic_box(
        index: arc4.Uint<64>,
        value: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    write_dynamic_arr_struct(
        index: arc4.Uint<64>,
        value: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    slice_box(

    ): void {
        err("stub only")
    }

    @abimethod
    arc4_box(

    ): void {
        err("stub only")
    }

    @abimethod
    test_box_ref(

    ): void {
        err("stub only")
    }

    @abimethod
    box_map_test(

    ): void {
        err("stub only")
    }

    @abimethod
    box_map_set(
        key: arc4.Uint<64>,
        value: arc4.Str,
    ): void {
        err("stub only")
    }

    @abimethod
    box_map_get(
        key: arc4.Uint<64>,
    ): arc4.Str {
        err("stub only")
    }

    @abimethod
    box_map_del(
        key: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    box_map_exists(
        key: arc4.Uint<64>,
    ): arc4.Bool {
        err("stub only")
    }
}
