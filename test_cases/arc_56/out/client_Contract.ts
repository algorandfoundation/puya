// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class SharedStruct extends arc4.Struct<{
    foo: arc4.DynamicBytes,
    bar: arc4.Uint<8>,
}> { }

export class TopLevelStruct extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Str,
    shared: SharedStruct,
}> { }

export class EventOnly extends arc4.Struct<{
    x: arc4.Uint<64>,
    y: arc4.Uint<64>,
}> { }

/**
 * Contract docstring
 */
export abstract class Contract extends Contract {

    /**
     * Method docstring
     */
    @abimethod({ allowActions: ['NoOp', 'OptIn'], onCreate: 'allow' })
    create(

    ): void {
        err("stub only")
    }

    /**
     * Method docstring2
     */
    @abimethod
    struct_arg(
        arg: TopLevelStruct,
        shared: SharedStruct,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod({ readonly: True })
    struct_return(
        arg: TopLevelStruct,
    ): SharedStruct {
        err("stub only")
    }

    @abimethod({ readonly: True })
    emits_error(
        arg: TopLevelStruct,
    ): void {
        err("stub only")
    }

    @abimethod
    emitter(

    ): void {
        err("stub only")
    }

    @abimethod
    conditional_emit(
        should_emit: arc4.Bool,
    ): void {
        err("stub only")
    }

    @abimethod
    template_value(

    ): arc4.Tuple<readonly [arc4.Tuple<readonly [arc4.DynamicBytes, arc4.Uint<8>]>, arc4.Uint<64>, arc4.Str, arc4.Uint<8>]> {
        err("stub only")
    }

    @abimethod
    with_constant_defaults(
        a: arc4.Uint<64>,
        b: arc4.Uint<64>,
        c: arc4.DynamicBytes,
        d: EventOnly,
        e: arc4.Tuple<readonly [arc4.Uint<64>, arc4.Str]>,
        f: FixedArray<arc4.Str, 2>,
        g: arc4.DynamicArray<arc4.Str>,
        h: arc4.Uint<64>,
        i: arc4.Uint<64>,
    ): void {
        err("stub only")
    }
}
