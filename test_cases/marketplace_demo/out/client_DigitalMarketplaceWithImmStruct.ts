// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class DigitalMarketplaceWithImmStruct extends Contract {

    @abimethod({ readonly: True })
    getListingsMbr(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod
    allowAsset(
        mbr_pay: gtxn.PaymentTxn,
        asset: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    firstDeposit(
        mbr_pay: gtxn.PaymentTxn,
        xfer: gtxn.AssetTransferTxn,
        unitary_price: arc4.Uint<64>,
        nonce: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    deposit(
        xfer: gtxn.AssetTransferTxn,
        nonce: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    setPrice(
        asset: arc4.Uint<64>,
        nonce: arc4.Uint<64>,
        unitary_price: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    buy(
        owner: arc4.Address,
        asset: arc4.Uint<64>,
        nonce: arc4.Uint<64>,
        buy_pay: gtxn.PaymentTxn,
        quantity: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    withdraw(
        asset: arc4.Uint<64>,
        nonce: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    bid(
        owner: arc4.Address,
        asset: arc4.Uint<64>,
        nonce: arc4.Uint<64>,
        bid_pay: gtxn.PaymentTxn,
        quantity: arc4.Uint<64>,
        unitary_price: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    acceptBid(
        asset: arc4.Uint<64>,
        nonce: arc4.Uint<64>,
    ): void {
        err("stub only")
    }
}
