// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class ContractTwo extends Contract {

    @abimethod
    renamed_some_method(

    ): void {
        err("stub only")
    }

    @abimethod
    test(

    ): arc4.Bool {
        err("stub only")
    }

    @abimethod({ resourceEncoding: 'index' })
    reference_types_index(
        pay: gtxn.PaymentTxn,
        asset: Asset,
        account: Account,
        app: Application,
        app_txn: gtxn.ApplicationCallTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    reference_types_value(
        pay: gtxn.PaymentTxn,
        asset: arc4.Uint<64>,
        account: arc4.Address,
        app: arc4.Uint<64>,
        app_txn: gtxn.ApplicationCallTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    test_tuple(
        val: arc4.Tuple<readonly [arc4.Uint<64>, arc4.UFixed<64, 10>, FixedArray<arc4.Uint<64>, 3>, arc4.DynamicArray<arc4.Uint<32>>, arc4.Bool, arc4.Address, FixedArray<arc4.Byte, 16>]>,
    ): arc4.Tuple<readonly [arc4.Uint<64>, arc4.UFixed<64, 10>, FixedArray<arc4.Uint<64>, 3>, arc4.DynamicArray<arc4.Uint<32>>, arc4.Bool, arc4.Address, FixedArray<arc4.Byte, 16>]> {
        err("stub only")
    }
}
