from algopy import (
    Account,
    ARC4Contract,
    Asset,
    Global,
    LocalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
)


class AuctionContract(ARC4Contract):
    def __init__(self) -> None:
        self.auction_end = UInt64(0)
        self.previous_bid = UInt64(0)
        self.asa_amount = UInt64(0)
        self.asa = Asset()
        self.previous_bidder = Account()
        self.claimable_amount = LocalState(UInt64, key="claim", description="The claimable amount")

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert Txn.sender == Global.creator_address, "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert self.asa.id == 0, "ASA already opted in"
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
        assert Txn.sender == Global.creator_address, "auction must be started by creator"

        # Ensure the auction hasn't already been started
        assert self.auction_end == 0, "auction already started"

        # Verify axfer
        assert (
            axfer.asset_receiver == Global.current_application_address
        ), "axfer must transfer to this app"

        # Set global state
        self.asa_amount = axfer.asset_amount
        self.auction_end = Global.latest_timestamp + length
        self.previous_bid = starting_price

    @arc4.abimethod
    def opt_in(self) -> None:
        pass

    @arc4.abimethod
    def bid(self, pay: gtxn.PaymentTransaction) -> None:
        # Ensure auction hasn't ended
        assert Global.latest_timestamp < self.auction_end, "auction has ended"

        # Verify payment transaction
        assert pay.sender == Txn.sender, "payment sender must match transaction sender"
        assert pay.amount > self.previous_bid, "Bid must be higher than previous bid"

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

    @arc4.abimethod
    def claim_asset(self, asset: Asset) -> None:
        assert Global.latest_timestamp > self.auction_end, "auction has not ended"
        # Send ASA to previous bidder
        itxn.AssetTransfer(
            xfer_asset=asset,
            asset_close_to=self.previous_bidder,
            asset_receiver=self.previous_bidder,
            asset_amount=self.asa_amount,
        ).submit()

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def delete_application(self) -> None:
        itxn.Payment(
            receiver=Global.creator_address,
            close_remainder_to=Global.creator_address,
        ).submit()

    def clear_state_program(self) -> bool:
        return True
