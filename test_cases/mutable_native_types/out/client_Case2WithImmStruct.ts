// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class NamedTup extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
}> { }

export abstract class Case2WithImmStruct extends Contract {

    @abimethod
    create_box(

    ): void {
        err("stub only")
    }

    @abimethod
    num_tups(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    add_tup(
        tup: NamedTup,
    ): void {
        err("stub only")
    }

    @abimethod
    get_tup(
        index: arc4.Uint<64>,
    ): NamedTup {
        err("stub only")
    }

    @abimethod
    sum(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    add_many_tups(
        tups: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>>,
    ): void {
        err("stub only")
    }

    @abimethod
    add_fixed_tups(
        tups: FixedArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>, 3>,
    ): void {
        err("stub only")
    }

    @abimethod
    set_a(
        a: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    set_b(
        b: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    get_3_tups(
        start: arc4.Uint<64>,
    ): FixedArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>, 3> {
        err("stub only")
    }

    @abimethod
    get_all_tups(

    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>> {
        err("stub only")
    }
}
