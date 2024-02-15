from puyapy import (
    ARC4Contract,
    Asset,
    AssetTransferTransaction,
    LocalState,
    PaymentTransaction,
    TransactionType,
    UInt64,
    arc4,
    op,
    subroutine,
)


class Auction(ARC4Contract):
    def __init__(self) -> None:
        self.auction_end = UInt64(0)
        self.previous_bid = UInt64(0)
        self.asa_amount = UInt64(0)
        self.asa = Asset(0)
        # Use zero address rather than an empty string for Account type safety
        self.previous_bidder = op.Global.zero_address
        self.claimable_amount = LocalState(UInt64)

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert op.Transaction.sender == op.Global.creator_address, "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert self.asa.asset_id == 0, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        op.CreateInnerTransaction.begin()
        op.CreateInnerTransaction.set_type_enum(TransactionType.AssetTransfer)
        op.CreateInnerTransaction.set_fee(0)  # cover fee with outer txn
        op.CreateInnerTransaction.set_asset_receiver(op.Global.current_application_address)
        op.CreateInnerTransaction.set_xfer_asset(asset.asset_id)
        op.CreateInnerTransaction.submit()

    @arc4.abimethod
    def start_auction(
        self, starting_price: arc4.UInt64, length: arc4.UInt64, axfer: AssetTransferTransaction
    ) -> None:
        assert (
            op.Transaction.sender == op.Global.creator_address
        ), "auction must be started by creator"

        # Ensure the auction hasn't already been started
        assert self.auction_end == 0, "auction already started"

        # Verify axfer
        assert (
            axfer.asset_receiver == op.Global.current_application_address
        ), "axfer must transfer to this app"

        # Set global state
        self.asa_amount = axfer.asset_amount
        self.auction_end = op.Global.latest_timestamp + length.decode()
        self.previous_bid = starting_price.decode()

    @arc4.abimethod
    def opt_in(self) -> None:
        pass

    @arc4.abimethod
    def bid(self, pay: PaymentTransaction) -> None:
        # Ensure auction hasn't ended
        assert op.Global.latest_timestamp < self.auction_end, "auction has ended"

        # Verify payment transaction
        assert pay.sender == op.Transaction.sender, "payment sender must match transaction sender"
        assert pay.amount > self.previous_bid, "Bid must be higher than previous bid"

        # set global state
        self.previous_bid = pay.amount
        self.previous_bidder = pay.sender

        # Update claimable amount
        self.claimable_amount[op.Transaction.sender] = pay.amount

    @arc4.abimethod
    def claim_bids(self) -> None:
        original_amount = self.claimable_amount[op.Transaction.sender]

        amount = original_amount

        # subtract previous bid if sender is previous bidder
        if op.Transaction.sender == self.previous_bidder:
            amount -= self.previous_bid

        op.CreateInnerTransaction.begin()
        op.CreateInnerTransaction.set_type_enum(TransactionType.Payment)
        op.CreateInnerTransaction.set_fee(0)  # cover fee with outer txn
        op.CreateInnerTransaction.set_receiver(op.Transaction.sender)
        op.CreateInnerTransaction.set_asset_amount(amount)
        op.CreateInnerTransaction.submit()

        self.claimable_amount[op.Transaction.sender] = original_amount - amount

    @arc4.abimethod
    def claim_asset(self, asset: Asset) -> None:
        assert op.Global.latest_timestamp > self.auction_end, "auction has not ended"

        # Send ASA to previous bidder
        op.CreateInnerTransaction.begin()
        op.CreateInnerTransaction.set_type_enum(TransactionType.AssetTransfer)
        op.CreateInnerTransaction.set_fee(0)  # cover fee with outer txn
        op.CreateInnerTransaction.set_asset_receiver(self.previous_bidder)
        op.CreateInnerTransaction.set_xfer_asset(asset.asset_id)
        op.CreateInnerTransaction.set_asset_amount(self.asa_amount)
        op.CreateInnerTransaction.set_asset_close_to(self.previous_bidder)
        op.CreateInnerTransaction.submit()

    @subroutine
    def delete_application(self) -> None:
        op.CreateInnerTransaction.begin()
        op.CreateInnerTransaction.set_type_enum(TransactionType.Payment)
        op.CreateInnerTransaction.set_fee(0)  # cover fee with outer txn
        op.CreateInnerTransaction.set_receiver(op.Global.creator_address)
        op.CreateInnerTransaction.set_close_remainder_to(op.Global.creator_address)
        op.CreateInnerTransaction.submit()

    def clear_state_program(self) -> bool:
        return True
