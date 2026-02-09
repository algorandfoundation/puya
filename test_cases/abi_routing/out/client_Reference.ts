// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class Reference extends Contract {

    @abimethod
    noop_with_uint64(
        a: arc4.Uint<64>,
    ): arc4.Uint<8> {
        err("stub only")
    }

    @abimethod({ allowActions: ['OptIn'] })
    opt_in(
        uint: arc4.Uint<64>,
        bites: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    @abimethod({ readonly: True, allowActions: ['NoOp', 'OptIn', 'CloseOut', 'UpdateApplication', 'DeleteApplication'], onCreate: 'allow' })
    all_the_things(
        a: arc4.Uint<64>,
    ): arc4.Uint<8> {
        err("stub only")
    }

    @abimethod({ readonly: True, allowActions: ['NoOp', 'CloseOut', 'DeleteApplication'] })
    mixed_oca(
        a: arc4.Uint<64>,
    ): arc4.Uint<8> {
        err("stub only")
    }

    @abimethod
    opt_into_asset(
        asset: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    with_transactions(
        asset: arc4.Uint<64>,
        an_int: arc4.Uint<64>,
        pay: gtxn.PaymentTxn,
        another_int: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    compare_assets(
        asset_a: arc4.Uint<64>,
        asset_b: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod({ readonly: True })
    get_address(

    ): arc4.Address {
        err("stub only")
    }

    @abimethod({ readonly: True })
    get_asset(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod({ readonly: True })
    get_application(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod({ readonly: True })
    get_an_int(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    method_with_default_args(
        asset_from_storage: arc4.Uint<64>,
        asset_from_function: arc4.Uint<64>,
        account_from_storage: arc4.Address,
        account_from_function: arc4.Address,
        application_from_storage: arc4.Uint<64>,
        application_from_function: arc4.Uint<64>,
        bytes_from_storage: FixedArray<arc4.Byte, 3>,
        int_from_storage: arc4.Uint<64>,
        int_from_function: arc4.Uint<64>,
        int_from_const: arc4.Uint<32>,
        str_from_const: arc4.Str,
        int_from_local: arc4.Uint<64>,
        bytes_from_local: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }

    /**
     * Fifteen args should not encode the last argument as a tuple
     */
    @abimethod
    method_with_15_args(
        one: arc4.Uint<64>,
        two: arc4.Uint<64>,
        three: arc4.Uint<64>,
        four: arc4.Uint<64>,
        five: arc4.Uint<64>,
        six: arc4.Uint<64>,
        seven: arc4.Uint<64>,
        eight: arc4.Uint<64>,
        nine: arc4.Uint<64>,
        ten: arc4.Uint<64>,
        eleven: arc4.Uint<64>,
        twelve: arc4.Uint<64>,
        thirteen: arc4.Uint<64>,
        fourteen: arc4.Uint<64>,
        fifteen: arc4.DynamicBytes,
    ): arc4.DynamicBytes {
        err("stub only")
    }

    /**
     * Application calls only support 16 args, and arc4 calls utilise the first arg for the method
     * selector. Args beyond this number are packed into a tuple and placed in the 16th slot.
     */
    @abimethod
    method_with_more_than_15_args(
        a: arc4.Uint<64>,
        b: arc4.Uint<64>,
        c: arc4.Uint<64>,
        d: arc4.Uint<64>,
        asset: arc4.Uint<64>,
        e: arc4.Uint<64>,
        f: arc4.Uint<64>,
        pay: gtxn.PaymentTxn,
        g: arc4.Uint<64>,
        h: arc4.Uint<64>,
        i: arc4.Uint<64>,
        j: arc4.Uint<64>,
        k: arc4.Uint<64>,
        l: arc4.Uint<64>,
        m: arc4.Uint<64>,
        n: arc4.Uint<64>,
        o: arc4.Uint<64>,
        p: arc4.Uint<64>,
        q: arc4.Uint<64>,
        r: arc4.Uint<64>,
        s: arc4.DynamicBytes,
        t: arc4.DynamicBytes,
        asset2: arc4.Uint<64>,
        pay2: gtxn.PaymentTxn,
        u: arc4.Uint<64>,
        v: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    hello_with_algopy_string(
        name: arc4.Str,
    ): arc4.Str {
        err("stub only")
    }
}
