from algopy import Bytes, TransactionType, Txn, arc4, itxn, op


class BoolOnly(arc4.ARC4Contract):
    @arc4.abimethod()
    def set_0_convert(self, inp: Bytes) -> Bytes:
        return op.setbit_bytes(inp, 0, bool(Txn.num_app_args))

    @arc4.abimethod()
    def set_0_compare(self, inp: Bytes) -> Bytes:
        return op.setbit_bytes(inp, 0, Txn.num_app_args > 0)

    @arc4.abimethod()
    def bool_only_properties(self) -> None:
        op.ITxnCreate.begin()
        op.ITxnCreate.set_type_enum(TransactionType.AssetConfig)
        op.ITxnCreate.set_config_asset_default_frozen(bool(Txn.num_app_args))
        op.ITxnCreate.submit()

        itxn.KeyRegistration(
            non_participation=True,
        ).submit()
