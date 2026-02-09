// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class TxnContract extends Contract {

    @abimethod
    call_with_txn(
        a: arc4.DynamicBytes,
        acfg: gtxn.Transaction,
        b: arc4.DynamicBytes,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    call_with_acfg(
        a: arc4.DynamicBytes,
        acfg: gtxn.AssetConfigTxn,
        b: arc4.DynamicBytes,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    call_with_acfg_no_return(
        a: arc4.DynamicBytes,
        acfg: gtxn.AssetConfigTxn,
        b: arc4.DynamicBytes,
    ): void {
        err("stub only")
    }
}
