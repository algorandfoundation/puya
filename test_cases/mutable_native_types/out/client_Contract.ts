// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class Payment extends arc4.Struct<{
    receiver: arc4.Address,
    asset: arc4.Uint<64>,
    amt: arc4.Uint<64>,
}> { }

export class FixedStruct extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
}> { }

export class NamedTup extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
}> { }

export abstract class Contract extends Contract {

    @abimethod
    test_imm_fixed_array(

    ): void {
        err("stub only")
    }

    @abimethod
    fixed_initialize(

    ): void {
        err("stub only")
    }

    @abimethod
    add_payment(
        pay: Payment,
    ): void {
        err("stub only")
    }

    @abimethod
    increment_payment(
        index: arc4.Uint<64>,
        amt: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    create_storage(
        box_key: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    local_struct(

    ): Payment {
        err("stub only")
    }

    @abimethod
    delete_storage(
        box_key: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    struct_arg(
        box_key: arc4.Uint<64>,
        a: FixedStruct,
    ): void {
        err("stub only")
    }

    @abimethod
    struct_return(

    ): FixedStruct {
        err("stub only")
    }

    @abimethod
    tup_return(

    ): NamedTup {
        err("stub only")
    }

    @abimethod
    calculate_sum(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    test_arr(
        arr: arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>>,
    ): arc4.DynamicArray<arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]>> {
        err("stub only")
    }

    @abimethod
    test_match_struct(
        arg: FixedStruct,
    ): arc4.Bool {
        err("stub only")
    }
}
