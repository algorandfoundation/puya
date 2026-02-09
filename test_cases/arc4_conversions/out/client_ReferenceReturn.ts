// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class ReferenceReturn extends Contract {

    @abimethod
    acc_ret(

    ): arc4.Address {
        err("stub only")
    }

    @abimethod
    asset_ret(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    app_ret(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    store(
        acc: arc4.Address,
        app: arc4.Uint<64>,
        asset: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    store_apps(
        apps: arc4.DynamicArray<arc4.Uint<64>>,
    ): void {
        err("stub only")
    }

    @abimethod
    store_assets(
        assets: arc4.DynamicArray<arc4.Uint<64>>,
    ): void {
        err("stub only")
    }

    @abimethod
    store_accounts(
        accounts: arc4.DynamicArray<arc4.Address>,
    ): void {
        err("stub only")
    }

    @abimethod
    return_apps(

    ): arc4.DynamicArray<arc4.Uint<64>> {
        err("stub only")
    }

    @abimethod
    return_assets(

    ): arc4.DynamicArray<arc4.Uint<64>> {
        err("stub only")
    }

    @abimethod
    return_accounts(

    ): arc4.DynamicArray<arc4.Address> {
        err("stub only")
    }
}
