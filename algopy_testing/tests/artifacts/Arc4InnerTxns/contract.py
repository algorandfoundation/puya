from algopy import ARC4Contract, Asset, Global, arc4, itxn


class Arc4InnerTxnsContract(ARC4Contract):
    @arc4.abimethod
    def opt_in_dummy_asset(self, asset: Asset) -> None:
        # Submit opt-in transaction: 0 asset transfer to self
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
        ).submit()
