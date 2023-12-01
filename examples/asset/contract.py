from algopy import (
    Asset,
    Contract,
    CreateInnerTransaction,
    Global,
    Transaction,
    TransactionType,
    UInt64,
    subroutine,
)


class Reference(Contract):
    def __init__(self) -> None:
        self.asa = Asset(0)

    def approval_program(self) -> bool:
        if Transaction.num_app_args() == 1:
            if Transaction.application_args(0) == b"opt_in":
                asset = Asset(Transaction.assets(0))
                self.opt_into_asset(asset)
            elif Transaction.application_args(0) == b"is_opted_in":
                asset = Asset(Transaction.assets(0))
                self.is_opted_asset(asset)
            else:
                assert False, "Expected opt_in or is_opted_in"
        return True

    def clear_state_program(self) -> bool:
        return True

    @subroutine
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert Transaction.sender() == Global.creator_address(), "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert not self.asa, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.AssetTransfer)
        CreateInnerTransaction.set_fee(UInt64(0))  # cover fee with outer txn
        CreateInnerTransaction.set_asset_receiver(Global.current_application_address())
        CreateInnerTransaction.set_xfer_asset(asset.asset_id)
        CreateInnerTransaction.submit()

    @subroutine
    def is_opted_asset(self, asset: Asset) -> None:
        assert self.asa == asset, "asset self.asa == asset"
