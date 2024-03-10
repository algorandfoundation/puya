from puyapy_mocks import Account, Asset, Bytes, UInt64
from puyapy_mocks._ctx_state import active_ctx


class AssetTransfer:
    def __init__(
        self,
        *,
        xfer_asset: Asset | UInt64 | int,
        asset_receiver: Account | str,
        asset_amount: UInt64 | int,
        asset_close_to: Account | str | None = None,
        sender: Account | str | None = None,
        fee: UInt64 | int | None = None,
        note: Bytes | bytes | None = None,
        rekey_to: Account | str | None = None,
    ) -> None:
        self.receiver = asset_receiver

        if sender is not None:
            self.sender = sender
        else:
            # We'd do this very differently in a real implementation
            self.sender = Account("contract")

        self.asset = xfer_asset
        self.asset_amount = asset_amount

    def submit(self):
        if isinstance(self.receiver, Account):
            receiver_address = self.receiver.address
        else:
            receiver_address = self.receiver

        if isinstance(self.sender, Account):
            sender_address = self.sender.address
        else:
            sender_address = self.sender

        if isinstance(self.asset, Asset):
            asset_id = self.asset.id
        else:
            asset_id = int(self.asset)

        # This doesn't account for any fees

        active_ctx().adjust_balance(receiver_address, asset_id, int(self.asset_amount))
        active_ctx().adjust_balance(sender_address, asset_id, -int(self.asset_amount))
