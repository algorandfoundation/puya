// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class StaticSizeContract extends Contract {

    @abimethod
    test_array(
        x1: arc4.Uint<64>,
        y1: arc4.Uint<64>,
        x2: arc4.Uint<64>,
        y2: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    test_extend_from_tuple(
        some_more: arc4.Tuple<readonly [arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>, arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>]>,
    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>> {
        err("stub only")
    }

    @abimethod
    test_extend_from_arc4_tuple(
        some_more: arc4.Tuple<readonly [arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>, arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>]>,
    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>> {
        err("stub only")
    }

    @abimethod
    test_bool_array(
        length: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    test_arc4_conversion(
        length: arc4.Uint<64>,
    ): arc4.DynamicArray<arc4.Uint<64>> {
        err("stub only")
    }

    @abimethod
    sum_array(
        arc4_arr: arc4.DynamicArray<arc4.Uint<64>>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    test_arc4_bool(

    ): arc4.DynamicArray<arc4.Bool> {
        err("stub only")
    }
}
