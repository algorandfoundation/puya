from algopy import (
    ARC4Contract,
    AssetTransferTransaction,
    CreateInnerTransaction,
    Global,
    Local,
    PaymentTransaction,
    Transaction,
    TransactionType,
    UInt64,
    arc4,
    subroutine,
)
from algopy._reference import Asset


class Auction(ARC4Contract):
    def __init__(self) -> None:
        self.auction_end = UInt64(0)
        self.previous_bid = UInt64(0)
        self.asa_amount = UInt64(0)
        self.asa = Asset(0)
        # Use zero address rather than an empty string for Account type safety
        self.previous_bidder = Global.zero_address()
        self.claimable_amount = Local(UInt64)

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert Transaction.sender() == Global.creator_address(), "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert self.asa.asset_id == 0, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.AssetTransfer)
        CreateInnerTransaction.set_fee(UInt64(0))  # cover fee with outer txn
        CreateInnerTransaction.set_asset_receiver(Global.current_application_address())
        CreateInnerTransaction.set_xfer_asset(asset.asset_id)
        CreateInnerTransaction.submit()

    @arc4.abimethod
    def start_auction(
        self, starting_price: arc4.UInt64, length: arc4.UInt64, axfer: AssetTransferTransaction
    ) -> None:
        assert (
            Transaction.sender() == Global.creator_address()
        ), "auction must be started by creator"

        # Ensure the auction hasn't already been started
        assert self.auction_end == 0, "auction already started"

        # Verify axfer
        assert (
            axfer.asset_receiver == Global.current_application_address()
        ), "axfer must transfer to this app"

        # Set global state
        self.asa_amount = axfer.asset_amount
        self.auction_end = Global.latest_timestamp() + length.decode()
        self.previous_bid = starting_price.decode()

    @arc4.abimethod
    def opt_in(self) -> None:
        pass

    @arc4.abimethod
    def bid(self, pay: PaymentTransaction) -> None:
        # Ensure auction hasn't ended
        assert Global.latest_timestamp() < self.auction_end, "auction has ended"

        # Verify payment transaction
        assert pay.sender == Transaction.sender(), "payment sender must match transaction sender"
        assert pay.amount > self.previous_bid, "Bid must be higher than previous bid"

        # set global state
        self.previous_bid = pay.amount
        self.previous_bidder = pay.sender

        # Update claimable amount
        self.claimable_amount[Transaction.sender()] = pay.amount

    @arc4.abimethod
    def claim_bids(self) -> None:
        original_amount = self.claimable_amount[Transaction.sender()]

        amount = original_amount

        # subtract previous bid if sender is previous bidder
        if Transaction.sender() == self.previous_bidder:
            amount -= self.previous_bid

        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.Payment)
        CreateInnerTransaction.set_fee(UInt64(0))  # cover fee with outer txn
        CreateInnerTransaction.set_receiver(Transaction.sender())
        CreateInnerTransaction.set_asset_amount(amount)
        CreateInnerTransaction.submit()

        self.claimable_amount[Transaction.sender()] = original_amount - amount

    @arc4.abimethod
    def claim_asset(self, asset: Asset) -> None:
        assert Global.latest_timestamp() > self.auction_end, "auction has not ended"

        # Send ASA to previous bidder
        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.AssetTransfer)
        CreateInnerTransaction.set_fee(UInt64(0))  # cover fee with outer txn
        CreateInnerTransaction.set_asset_receiver(self.previous_bidder)
        CreateInnerTransaction.set_xfer_asset(asset.asset_id)
        CreateInnerTransaction.set_asset_amount(self.asa_amount)
        CreateInnerTransaction.set_asset_close_to(self.previous_bidder)
        CreateInnerTransaction.submit()

    @subroutine
    def delete_application(self) -> None:
        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.Payment)
        CreateInnerTransaction.set_fee(UInt64(0))  # cover fee with outer txn
        CreateInnerTransaction.set_receiver(Global.creator_address())
        CreateInnerTransaction.set_close_remainder_to(Global.creator_address())
        CreateInnerTransaction.submit()

    def clear_state_program(self) -> bool:
        return True
