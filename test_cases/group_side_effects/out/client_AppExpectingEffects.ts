// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class AppExpectingEffects extends Contract {

    @abimethod
    create_group(
        asset_create: gtxn.AssetConfigTxn,
        app_create: gtxn.ApplicationCallTxn,
    ): arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]> {
        err("stub only")
    }

    @abimethod
    log_group(
        app_call: gtxn.ApplicationCallTxn,
    ): void {
        err("stub only")
    }
}
