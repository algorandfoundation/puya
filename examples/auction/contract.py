from algopy import (
    ARC4Contract,
    Asset,
    Global,
    LocalState,
    OnCompleteAction,
    TemplateVar,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
)


class Auction(ARC4Contract):
    def __init__(self) -> None:
        self.auction_end = UInt64(0)
        self.previous_bid = UInt64(0)
        self.asa_amount = UInt64(0)
        self.asa = Asset()
        self.previous_bidder = Global.creator_address
        self.claimable_amount = LocalState(UInt64, key="claim", description="The claimable amount")

    @arc4.baremethod
    def create(self) -> None:
        """Creates the contract without choosing an ASA to auction yet."""

    @arc4.abimethod(create="allow")
    def opt_into_asset(self, asset: Asset) -> None:
        """
        Sets the ASA to be auctioned, this must be called before starting the auction
        so that the contract can receive the ASA transfer.
        This method can be invoked on creation to save a transaction.
        """
        assert Txn.sender == Global.creator_address
        # ensure auction hasn't started
        assert self.auction_end == 0, "auction already started"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
        ).submit()

    @arc4.abimethod
    def start_auction(
        self,
        starting_price: UInt64,
        length: UInt64,
        axfer: gtxn.AssetTransferTransaction,
    ) -> None:
        assert Txn.sender == Global.creator_address

        # Ensure the auction hasn't already been started
        assert self.auction_end == 0, "auction already started"

        # Verify axfer
        assert (
            axfer.asset_receiver == Global.current_application_address
        ), "axfer must transfer to this app"
        assert axfer.xfer_asset == self.asa

        # Set global state
        self.asa_amount = axfer.asset_amount
        self.auction_end = Global.latest_timestamp + length
        # set the previous bidder to the creator, so that if the auction ends
        # without a successful bid, the creator can reclaim it
        self.previous_bidder = Global.creator_address
        self.previous_bid = starting_price

    @arc4.baremethod(allow_actions=[OnCompleteAction.UpdateApplication])
    def update(self) -> None:
        """
        Allow creator to update the application if configured to be updatable at deploy time.

        This is useful during development, but probably should not be enabled in production.
        """
        assert Txn.sender == Global.creator_address
        assert TemplateVar[bool]("UPDATABLE")

    @arc4.abimethod(
        allow_actions=[OnCompleteAction.DeleteApplication],
        default_args={"_asset": "asa"},  # TODO: does this work if ASA is zero?
    )
    def delete(self, _asset: Asset) -> None:
        """Allows the creator to delete this contract, provided the auction is not in progress,
        and the contract no longer holds the asset under auction if there is one."""
        assert Txn.sender == Global.creator_address
        if self.auction_end != 0:
            assert (
                self.auction_end == 0 or Global.latest_timestamp > self.auction_end
            ), "auction is in progress"
            assert (
                self.asa.balance(Global.current_application_address) == 0
            ), "ASA has not been claimed"
        # Allow creator to withdraw all remaining ALGO
        itxn.Payment(
            receiver=Global.creator_address,
            close_remainder_to=Global.creator_address,
        ).submit()

    @arc4.abimethod(allow_actions=[OnCompleteAction.OptIn])
    def opt_in(self) -> None:
        pass

    @arc4.abimethod(allow_actions=[OnCompleteAction.OptIn])
    def bid(self, pay: gtxn.PaymentTransaction) -> None:
        # Ensure auction hasn't ended
        assert Global.latest_timestamp < self.auction_end, "auction has ended"

        # Verify payment transaction
        assert pay.sender == Txn.sender, "payment sender must match transaction sender"
        assert pay.amount > self.previous_bid, "Bid must be higher than previous bid"
        assert pay.receiver == Global.current_application_address

        # set global state
        self.previous_bid = pay.amount
        self.previous_bidder = pay.sender

        # Update claimable amount
        self.claimable_amount[Txn.sender] = pay.amount

    @arc4.abimethod
    def claim_bids(self) -> None:
        amount = original_amount = self.claimable_amount[Txn.sender]

        # subtract previous bid if sender is previous bidder
        if Txn.sender == self.previous_bidder:
            amount -= self.previous_bid

        itxn.Payment(
            amount=amount,
            receiver=Txn.sender,
        ).submit()

        self.claimable_amount[Txn.sender] = original_amount - amount

    @arc4.abimethod(default_args={"_asset": "asa"})
    def claim_asset(self, _asset: Asset) -> None:
        """
        Once the auction is over, this transfers the ASA to the successful bidder,
        or returns it to the creator if there were no successful bids.

        Note that the recipient must be opted into the asset for this to succeed.
        """
        assert Global.latest_timestamp > self.auction_end, "auction has not ended"
        # Send ASA to previous bidder
        itxn.AssetTransfer(
            xfer_asset=self.asa,
            asset_close_to=self.previous_bidder,
            asset_receiver=self.previous_bidder,
            asset_amount=self.asa_amount,
        ).submit()
