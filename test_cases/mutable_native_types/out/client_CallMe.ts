// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class FixedStruct extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
}> { }

export class NestedStruct extends arc4.Struct<{
    fixed: FixedStruct,
    c: arc4.Uint<64>,
}> { }

export class DynamicStruct extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
    c: arc4.DynamicBytes,
    d: arc4.Str,
    e: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>>,
}> { }

export abstract class CallMe extends Contract {

    @abimethod({ allowActions: ['DeleteApplication'] })
    delete(

    ): void {
        err("stub only")
    }

    @abimethod
    fixed_struct_arg(
        arg: FixedStruct,
    ): void {
        err("stub only")
    }

    @abimethod
    fixed_struct_ret(

    ): FixedStruct {
        err("stub only")
    }

    @abimethod
    nested_struct_arg(
        arg: NestedStruct,
    ): void {
        err("stub only")
    }

    @abimethod
    nested_struct_ret(

    ): NestedStruct {
        err("stub only")
    }

    @abimethod
    dynamic_struct_arg(
        arg: DynamicStruct,
    ): void {
        err("stub only")
    }

    @abimethod
    dynamic_struct_ret(

    ): DynamicStruct {
        err("stub only")
    }

    @abimethod
    fixed_arr_arg(
        arg: FixedArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>, 3>,
    ): void {
        err("stub only")
    }

    @abimethod
    fixed_arr_ret(

    ): FixedArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>, 3> {
        err("stub only")
    }

    @abimethod
    native_arr_arg(
        arg: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>>,
    ): void {
        err("stub only")
    }

    @abimethod
    native_arr_ret(

    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>> {
        err("stub only")
    }

    @abimethod
    log_it(

    ): void {
        err("stub only")
    }
}
