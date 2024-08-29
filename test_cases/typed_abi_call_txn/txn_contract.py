from algopy import (
    ARC4Contract,
    Bytes,
    TransactionType,
    UInt64,
    arc4,
    gtxn,
)


class TxnContract(ARC4Contract):
    @arc4.abimethod
    def call_with_txn(self, a: Bytes, acfg: gtxn.Transaction, b: Bytes) -> UInt64:
        assert a == b"a", "a is not a"
        assert b == b"b", "b is not b"
        assert acfg.type == TransactionType.AssetConfig, "expected asset config"
        assert acfg.created_asset.id, "expected asset id"
        return acfg.created_asset.id

    @arc4.abimethod
    def call_with_acfg(self, a: Bytes, acfg: gtxn.AssetConfigTransaction, b: Bytes) -> UInt64:
        assert a == b"a", "a is not a"
        assert b == b"b", "b is not b"
        assert acfg.created_asset.id, "expected asset id"
        return acfg.created_asset.id
