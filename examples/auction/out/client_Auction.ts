// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class Auction extends Contract {

    @abimethod
    opt_into_asset(
        asset: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    start_auction(
        starting_price: arc4.Uint<64>,
        length: arc4.Uint<64>,
        axfer: gtxn.AssetTransferTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    opt_in(

    ): void {
        err("stub only")
    }

    @abimethod
    bid(
        pay: gtxn.PaymentTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    claim_bids(

    ): void {
        err("stub only")
    }

    @abimethod
    claim_asset(
        asset: arc4.Uint<64>,
    ): void {
        err("stub only")
    }
}
