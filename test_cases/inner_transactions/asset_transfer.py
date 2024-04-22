from algopy import (
    ARC4Contract,
    Global,
    arc4,
    itxn,
    op,
)


class CreateAndTransferContract(ARC4Contract):
    @arc4.abimethod()
    def create_and_transfer(self) -> None:
        # create
        new_asset = (
            itxn.AssetConfig(
                total=1000,
                asset_name="test",
                unit_name="TST",
                decimals=0,
                manager=op.Global.current_application_address,
                clawback=op.Global.current_application_address,
                fee=0,
            )
            .submit()
            .created_asset
        )

        # transfer
        itxn.AssetTransfer(
            asset_sender=new_asset.creator,
            asset_receiver=Global.current_application_address,
            asset_amount=1000,
            xfer_asset=new_asset,
            fee=0,
        ).submit()
