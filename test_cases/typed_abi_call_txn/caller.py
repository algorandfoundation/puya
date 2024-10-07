from algopy import (
    Application,
    ARC4Contract,
    Bytes,
    arc4,
    itxn,
    op,
)

from test_cases.typed_abi_call_txn.txn_contract import TxnContract


class Caller(ARC4Contract):
    @arc4.abimethod
    def test_call_with_txn(self, a: Bytes, b: Bytes, app: Application) -> None:
        txn = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            total=1,
        )
        asset_id, _txn = arc4.abi_call(
            TxnContract.call_with_txn,
            a,
            txn,
            b,
            app_id=app,
        )
        assert asset_id, "expected asset id"

    @arc4.abimethod
    def test_call_with_acfg(self, a: Bytes, b: Bytes, app: Application) -> None:
        txn = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            total=1,
        )
        arc4.abi_call(
            TxnContract.call_with_acfg,
            a,
            txn,
            b,
            app_id=app,
        )

    @arc4.abimethod
    def test_call_with_acfg_no_return(self, a: Bytes, b: Bytes, app: Application) -> None:
        acfg = itxn.AssetConfig(
            unit_name="TST",
            asset_name="TEST",
            total=1,
        )
        txn1 = arc4.abi_call(
            TxnContract.call_with_acfg_no_return, a, acfg, b, app_id=app, note=b"1"
        )
        assert txn1.note == b"1"
        txn1_copy1 = txn1
        assert txn1_copy1.note == txn1.note
        asset_id = op.GITxn.created_asset_id(0)
        assert asset_id, "expected asset to be created"
