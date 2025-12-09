from algopy import (
    Application,
    ARC4Contract,
    Bytes,
    UInt64,
    arc4,
    itxn,
    op,
)

from test_cases.typed_itxn_abi_call_txn.txn_contract import TxnContract


class Caller(ARC4Contract):
    @arc4.abimethod
    def test_call_with_txn(self, a: Bytes, b: Bytes, app: Application) -> None:
        txn = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            total=1,
        )
        app_call = itxn.abi_call(
            TxnContract.call_with_txn,
            a,
            txn,
            b,
            app_id=app,
        )
        app_call_txn = app_call.submit()
        asset_id = app_call_txn.result
        assert asset_id, "expected asset id"

    @arc4.abimethod
    def test_call_with_acfg(self, a: Bytes, b: Bytes, app: Application) -> None:
        txn = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            total=1,
        )
        app_call = itxn.abi_call(
            TxnContract.call_with_acfg,
            a,
            txn,
            b,
            app_id=app,
        )
        app_call.submit()

    @arc4.abimethod
    def test_call_with_infer(self, a: Bytes, b: Bytes, app: Application) -> None:
        txn = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            total=1,
        )
        app_call = itxn.abi_call[UInt64](
            "call_with_acfg",
            a,
            txn,
            b,
            app_id=app,
        )
        app_call.submit()

    @arc4.abimethod
    def test_call_with_acfg_no_return(self, a: Bytes, b: Bytes, app: Application) -> None:
        acfg = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            total=1,
        )
        app_call = itxn.abi_call(
            TxnContract.call_with_acfg_no_return, a, acfg, b, app_id=app, note=b"1"
        )
        txn1 = app_call.submit()
        assert txn1.note == b"1"
        txn1_copy1 = txn1
        assert txn1_copy1.note == txn1.note
        asset_id = op.GITxn.created_asset_id(0)
        assert asset_id, "expected asset to be created"
