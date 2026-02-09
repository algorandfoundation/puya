// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class TestTuple extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<512>,
    c: arc4.Str,
    d: arc4.DynamicBytes,
}> { }

export class UIntTestTuple extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
    c: arc4.Uint<64>,
}> { }

export abstract class NamedTuplesContract extends Contract {

    @abimethod
    build_tuple(
        a: arc4.Uint<64>,
        b: arc4.Uint<512>,
        c: arc4.Str,
        d: arc4.DynamicBytes,
    ): TestTuple {
        err("stub only")
    }

    @abimethod
    build_tuple_side_effects(

    ): UIntTestTuple {
        err("stub only")
    }

    @abimethod
    test_tuple(
        value: TestTuple,
    ): void {
        err("stub only")
    }
}
