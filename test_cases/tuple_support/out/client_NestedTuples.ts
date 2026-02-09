// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class Child extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.DynamicBytes,
    c: arc4.Str,
}> { }

export class Parent extends arc4.Struct<{
    foo: arc4.Uint<64>,
    foo_arc: arc4.Uint<64>,
    child: Child,
}> { }

export class ParentWithList extends arc4.Struct<{
    parent: Parent,
    children: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.DynamicBytes, arc4.Str]>>,
}> { }

export class SimpleTup extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
}> { }

export class TupleWithMutable extends arc4.Struct<{
    arr: arc4.DynamicArray<arc4.Uint<64>>,
    child: Child,
}> { }

export abstract class NestedTuples extends Contract {

    @abimethod
    store_tuple(
        pwl: ParentWithList,
    ): void {
        err("stub only")
    }

    @abimethod
    load_tuple(

    ): ParentWithList {
        err("stub only")
    }

    @abimethod
    store_tuple_in_box(
        key: SimpleTup,
    ): void {
        err("stub only")
    }

    @abimethod
    is_tuple_in_box(
        key: SimpleTup,
    ): arc4.Bool {
        err("stub only")
    }

    @abimethod
    load_tuple_from_box(
        key: SimpleTup,
    ): SimpleTup {
        err("stub only")
    }

    @abimethod
    maybe_load_tuple_from_box(
        key: SimpleTup,
    ): arc4.Tuple<readonly [arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>, arc4.Bool]> {
        err("stub only")
    }

    @abimethod
    load_tuple_from_box_or_default(
        key: SimpleTup,
    ): SimpleTup {
        err("stub only")
    }

    @abimethod
    load_tuple_from_local_state_or_default(
        key: arc4.Str,
    ): SimpleTup {
        err("stub only")
    }

    @abimethod
    mutate_local_tuple(

    ): TupleWithMutable {
        err("stub only")
    }

    @abimethod
    mutate_tuple_in_storage_currently_supported_method(

    ): void {
        err("stub only")
    }

    @abimethod
    run_tests(

    ): arc4.Bool {
        err("stub only")
    }

    @abimethod
    nested_tuple_params(
        args: arc4.Tuple<readonly [arc4.Str, arc4.Tuple<readonly [arc4.DynamicBytes, arc4.Tuple<readonly [arc4.Uint<64>]>]>]>,
    ): arc4.Tuple<readonly [arc4.DynamicBytes, arc4.Tuple<readonly [arc4.Str, arc4.Uint<64>]>]> {
        err("stub only")
    }

    @abimethod
    named_tuple(
        args: Child,
    ): Child {
        err("stub only")
    }

    @abimethod
    nested_named_tuple_params(
        args: Parent,
    ): Parent {
        err("stub only")
    }
}
