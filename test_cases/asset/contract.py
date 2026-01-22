from algopy import (
    Asset,
    Contract,
    TransactionType,
    UInt64,
    subroutine,
)
from algopy.op import (
    Global,
    ITxnCreate,
    Txn,
    bzero,
)


class Reference(Contract):
    def __init__(self) -> None:
        self.asa = Asset()

    def approval_program(self) -> bool:
        assert bool(Asset(1)) == bool(Asset(2))
        if Txn.num_app_args == 1:
            if Txn.application_args(0) == b"opt_in":
                asset = Txn.assets(0)
                self.opt_into_asset(asset)
            elif Txn.application_args(0) == b"is_opted_in":
                asset = Txn.assets(0)
                self.is_opted_asset(asset)
            else:
                assert False, "Expected opt_in or is_opted_in"
        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert Txn.sender == Global.creator_address, "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert not self.asa, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        ITxnCreate.begin()
        ITxnCreate.set_type_enum(TransactionType.AssetTransfer)
        ITxnCreate.set_fee(UInt64(0))  # cover fee with outer txn
        ITxnCreate.set_asset_receiver(Global.current_application_address)
        ITxnCreate.set_xfer_asset(asset)
        ITxnCreate.submit()

    @subroutine
    def is_opted_asset(self, asset: Asset) -> None:
        assert self.asa == asset, "asset self.asa == asset"
        assert asset.total == 10000000, "total"
        assert asset.decimals == 0, "decimals"
        assert not asset.default_frozen, "default frozen"
        assert asset.unit_name == b"a", "unit_name"
        assert asset.name == b"asset a", "name"
        assert asset.url == b"", "URL"
        assert asset.metadata_hash == bzero(32), "hash"
        assert asset.manager == Global.zero_address, "manager"
        assert asset.reserve == Global.zero_address, "reserve"
        assert asset.freeze == Global.zero_address, "freeze"
        assert asset.clawback == Global.zero_address, "clawback"
        assert asset.creator == Global.creator_address, "creator"
        assert Global.current_application_address.is_opted_in(asset), "asset opted in"
