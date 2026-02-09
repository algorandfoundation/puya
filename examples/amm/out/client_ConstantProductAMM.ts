// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class ConstantProductAMM extends Contract {

    /**
     * sets the governor of the contract, may only be called by the current governor
     */
    @abimethod
    set_governor(
        new_governor: arc4.Address,
    ): void {
        err("stub only")
    }

    /**
     * bootstraps the contract by opting into the assets and creating the pool token.
     * Note this method will fail if it is attempted more than once on the same contract since the assets and pool token application state values are marked as static and cannot be overridden.
     */
    @abimethod({ resourceEncoding: 'index' })
    bootstrap(
        seed: gtxn.PaymentTxn,
        a_asset: Asset,
        b_asset: Asset,
    ): arc4.Uint<64> {
        err("stub only")
    }

    /**
     * mint pool tokens given some amount of asset A and asset B.
     * Given some amount of Asset A and Asset B in the transfers, mint some number of pool tokens commensurate with the pools current balance and circulating supply of pool tokens.
     */
    @abimethod({ resourceEncoding: 'index' })
    mint(
        a_xfer: gtxn.AssetTransferTxn,
        b_xfer: gtxn.AssetTransferTxn,
        pool_asset: Asset,
        a_asset: Asset,
        b_asset: Asset,
    ): void {
        err("stub only")
    }

    /**
     * burn pool tokens to get back some amount of asset A and asset B
     */
    @abimethod({ resourceEncoding: 'index' })
    burn(
        pool_xfer: gtxn.AssetTransferTxn,
        pool_asset: Asset,
        a_asset: Asset,
        b_asset: Asset,
    ): void {
        err("stub only")
    }

    /**
     * Swap some amount of either asset A or asset B for the other
     */
    @abimethod({ resourceEncoding: 'index' })
    swap(
        swap_xfer: gtxn.AssetTransferTxn,
        a_asset: Asset,
        b_asset: Asset,
    ): void {
        err("stub only")
    }
}
