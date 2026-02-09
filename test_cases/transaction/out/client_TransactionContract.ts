// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class TransactionContract extends Contract {

    @abimethod({ onCreate: 'require' })
    create(

    ): void {
        err("stub only")
    }

    @abimethod
    pay(
        txn: gtxn.PaymentTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    key(
        txn: gtxn.KeyRegistrationTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    asset_config(
        txn: gtxn.AssetConfigTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    asset_transfer(
        txn: gtxn.AssetTransferTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    asset_freeze(
        txn: gtxn.AssetFreezeTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    application_call(
        txn: gtxn.ApplicationCallTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    multiple_txns(
        txn1: gtxn.ApplicationCallTxn,
        txn2: gtxn.ApplicationCallTxn,
        txn3: gtxn.ApplicationCallTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    any_txn(
        txn1: gtxn.Transaction,
        txn2: gtxn.Transaction,
        txn3: gtxn.Transaction,
    ): void {
        err("stub only")
    }

    @abimethod
    group_init(
        txn1: gtxn.Transaction,
        txn2: gtxn.Transaction,
        txn3: gtxn.Transaction,
    ): void {
        err("stub only")
    }
}
