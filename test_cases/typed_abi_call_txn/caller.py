from algopy import (
    Application,
    ARC4Contract,
    Bytes,
    arc4,
    itxn,
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
