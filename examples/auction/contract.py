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
        self.highest_bid = UInt64(0)
        self.asa = Asset()
        self.highest_bidder = Global.zero_address
        self.claimable_amount = LocalState(UInt64, key="claim", description="The claimable amount")

        # A "grace period" to claim an asset after an auction ended.
        # After this time, the creator may delete the application and get the asset.
        # They may also reclaim all unclaimed bidding money.
        self.claim_time = UInt64(10000)


    @arc4.baremethod(create="require")
    def create(self) -> None:
        """Creates the contract without choosing an ASA to auction yet."""


    # The explicit disallow is not necessary as this is the default option.
    @arc4.abimethod(create="disallow")
    def opt_into_asset(self, asset: Asset) -> None:
        """
        Sets the ASA to be auctioned, this must be called before starting the auction
        so that the contract can receive the ASA transfer.
        This method can be invoked on creation to save a transaction.
        """
        # creator admin privileges
        assert Txn.sender == Global.creator_address

        # ensure auction hasn't started
        assert self.auction_end == 0, "auction already started"

        # ensure we haven't picked an asset yet
        assert asset != Asset() and self.asa == Asset(), "an asset was already picked"
        # We could allow for switching the asset if the auction has not started yet.
        # In the "simplest" version we don't.

        # For this simple example, we disallow assets with clawback or freeze capabilities
        assert (asset.clawback == Global.zero_address and asset.freeze == Global.zero_address
                ), "clawback-able or freezable assets are disallowed in this simple auction"

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

        # creator admin privileges
        assert Txn.sender == Global.creator_address

        # Ensure the auction hasn't already been started
        assert self.auction_end == 0, "auction already started"

        # Ensure we have opted into an asset, and it is the asset being transfered
        # this would not happen as the transfer would fail anyways if not opted into,
        # but we make it explicit here
        assert axfer.xfer_asset == self.asa, "not the correct asset"

        # Verify axfer
        assert (
            axfer.asset_receiver == Global.current_application_address
        ), "axfer must transfer to this app"

        assert axfer.asset_amount > 0, "no auction should be for zero units of an asset"
        assert length > 0, "null auction time disallowed"

        # Set global state
        self.auction_end = Global.latest_timestamp + length

        # Set to zero address instead of creator address simply to allow the creator
        # to participate from the auction.
        self.highest_bidder = Global.zero_address
        self.highest_bid = starting_price


    @arc4.baremethod(allow_actions=[OnCompleteAction.UpdateApplication])
    def update(self) -> None:
        """
        Allow creator to update the application if configured to be updatable at deploy time.

        This is useful during development, but probably should not be enabled in production.
        """
        assert Txn.sender == Global.creator_address
        assert (self.auction_end == 0 and self.asa == Asset()
            ), "already opted into asset or started auction"
        assert TemplateVar[bool]("UPDATABLE")


    @arc4.abimethod(
        allow_actions=[OnCompleteAction.DeleteApplication],
    )
    def delete(self) -> None:
        """Allows the creator to delete this contract, provided the auction is not in progress,
        and the contract no longer holds the asset under auction if there is one."""

        # creator admin control
        assert Txn.sender == Global.creator_address

        #redundant
        # assert(
        #     Global.latest_timestamp > self.auction_end
        #     ), "auction is in progress"

        #either:
        # 1- auction has not started and no asa has been opted into, or
        # 2- asset has been opted into but it has already been claimed, or
        # 3- we are beyond the end and claim period time of the auction, which
        # has already taken place
        assert (
            self.asa == Asset() or
            self.asa.balance(Global.current_application_address) == 0 or
            (Global.latest_timestamp > self.auction_end + self.claim_time and
            self.auction_end > 0)
        ), "ASA has not been claimed and still in locked claim time"


        # Application opts out of the asset
        # any unclaimed leftover is transfered to the creator, as we
        # are beyond the grace period for winning claims
        if self.asa != Asset():
            itxn.AssetTransfer(
                xfer_asset = self.asa,
                asset_receiver=Global.caller_application_address,
                asset_amount=0,
                asset_close_to=Global.creator_address
            ).submit()

        # Allow creator to withdraw all remaining ALGO
        itxn.Payment(
            receiver=Global.creator_address,
            close_remainder_to=Global.creator_address,
        ).submit()


    @arc4.abimethod(allow_actions=[OnCompleteAction.OptIn])
    def opt_in(self) -> None:
        """enable users to opt into application, generating
        Local State for their account"""
        pass


    @arc4.abimethod(allow_actions=[OnCompleteAction.OptIn])
    def bid(self, pay: gtxn.PaymentTransaction) -> None:

        # Ensure auction hasn't ended
        assert Global.latest_timestamp < self.auction_end, "auction has ended"

        # Verify payment transaction
        assert pay.sender == Txn.sender, "payment sender must match transaction sender"
        assert pay.amount > self.highest_bid, "Bid must be higher than previous bid"
        assert (pay.receiver == Global.current_application_address
                ), "bid payment must go to the application"

        # if there was a legitimate bidder before, add to their re-claimable amount
        if self.highest_bidder != Global.zero_address:
            # in case the previous bidder force cleared their state, the bid should not fail
            (_, is_opted_in) = self.claimable_amount.maybe(self.highest_bidder)
            if is_opted_in:
                self.claimable_amount[self.highest_bidder] += self.highest_bid

        # set global state
        self.highest_bid = pay.amount
        self.highest_bidder = pay.sender

    @arc4.abimethod(allow_actions=[OnCompleteAction.CloseOut, OnCompleteAction.NoOp])
    def claim_bids(self) -> None:
        """
        At any time during the auction, an account may reclaim their accumulated
        past bid amounts that have been surpassed by other offers. This excludes
        the current highest bidder, who may not back down from their offer unless
        they are outbid.
        """
        amount = self.claimable_amount[Txn.sender]

        assert amount > 0, "no reclaimable bids registered for caller"

        assert (self.highest_bidder != Txn.sender
                ), "the highest bidder is not allowed to withdraw their bid"
        # Note that, if the highest bidder were to force clear their state, they would
        # not deadlock the contract, and if they are outbid they would forfeit a claim
        # to the whole amount they may have bid (which would be susceptible to collection
        # by the contract creator on deletion)

        # Claim the amount
        itxn.Payment(
            amount=amount,
            receiver=Txn.sender,
        ).submit()

        # Zero out bidder's claimable amount
        self.claimable_amount[Txn.sender] = UInt64(0)


    @arc4.abimethod
    def claim_asset(self) -> None:
        """
        Once the auction is over, this transfers the ASA to the successful bidder,
        or returns it to the creator if there were no successful bids.

        Note that the recipient must be opted into the asset for this to succeed.
        """
        assert Global.latest_timestamp > self.auction_end, "auction has not ended"

        # if there were no bids, give back to creator
        recipient = self.highest_bidder if self.highest_bidder != Global.zero_address else Global.creator_address

        # Send ASA to previous bidder
        # Optionally we could opt out of the asset here,
        # but instead we let the opt out happen on application deletion
        itxn.AssetTransfer(
            xfer_asset=self.asa,
            asset_receiver=recipient,
            asset_amount=self.asa.balance(Global.creator_address),
        ).submit()
