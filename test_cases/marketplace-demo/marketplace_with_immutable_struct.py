# ruff: noqa: N815
from algopy import (
    Account,
    Asset,
    BoxMap,
    Global,
    Struct,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    log,
    op,
    subroutine,
)


class ListingKey(
    Struct, frozen=True
):  # compare this, (Struct), (Struct, frozen=True), (MutableStruct),
    owner: Account
    asset: UInt64
    nonce: UInt64


class ListingValue(Struct, frozen=True):
    deposited: UInt64
    unitaryPrice: UInt64
    bidder: Account
    bid: UInt64
    bidUnitaryPrice: UInt64


class DigitalMarketplaceWithImmStruct(arc4.ARC4Contract):
    def __init__(self) -> None:
        log("init")
        self.listings = BoxMap(
            ListingKey, ListingValue, key_prefix=b"listings"
        )  # ok to have tuples as key definition?

    @subroutine
    def listings_box_mbr(self) -> UInt64:
        return UInt64(
            2_500
            +
            # fmt: off
            # Key length
            (
                8
                + 32
                + 8
                + 8
                +
                # Value length
                8
                + 8
                + 32
                + 8
                + 8
            )
            *
            # fmt: on
            400
        )

    @subroutine
    def quantity_price(self, quantity: UInt64, price: UInt64, asset_decimals: UInt64) -> UInt64:
        amount_not_scaled_high, amount_not_scaled_low = op.mulw(price, quantity)
        scaling_factor_high, scaling_factor_low = op.expw(10, asset_decimals)
        _quotient_high, amount_to_be_paid, _remainder_high, _remainder_low = op.divmodw(
            amount_not_scaled_high, amount_not_scaled_low, scaling_factor_high, scaling_factor_low
        )
        assert _quotient_high == 0

        return amount_to_be_paid

    @arc4.abimethod(readonly=True, name="getListingsMbr")
    def get_listings_mbr(self) -> UInt64:
        return self.listings_box_mbr()

    @arc4.abimethod(name="allowAsset")
    def allow_asset(self, mbr_pay: gtxn.PaymentTransaction, asset: Asset) -> None:
        assert not Global.current_application_address.is_opted_in(asset)

        assert mbr_pay.receiver == Global.current_application_address
        assert mbr_pay.amount == Global.asset_opt_in_min_balance

        itxn.AssetTransfer(
            xfer_asset=asset, asset_receiver=Global.current_application_address, asset_amount=0
        ).submit()

    @arc4.abimethod(name="firstDeposit")
    def first_deposit(
        self,
        mbr_pay: gtxn.PaymentTransaction,
        xfer: gtxn.AssetTransferTransaction,
        unitary_price: UInt64,
        nonce: UInt64,
    ) -> None:
        assert mbr_pay.sender == Txn.sender
        assert mbr_pay.receiver == Global.current_application_address
        assert mbr_pay.amount == self.listings_box_mbr()

        key = ListingKey(owner=Txn.sender, asset=xfer.xfer_asset.id, nonce=nonce)
        assert key not in self.listings

        assert xfer.sender == Txn.sender
        assert xfer.asset_receiver == Global.current_application_address
        assert xfer.asset_amount > 0

        self.listings[key] = ListingValue(
            deposited=xfer.asset_amount,
            unitaryPrice=unitary_price,
            bidder=Account(),
            bid=UInt64(),
            bidUnitaryPrice=UInt64(),
        )

    @arc4.abimethod
    def deposit(self, xfer: gtxn.AssetTransferTransaction, nonce: UInt64) -> None:
        key = ListingKey(owner=Txn.sender, asset=xfer.xfer_asset.id, nonce=nonce)

        assert xfer.sender == Txn.sender
        assert xfer.asset_receiver == Global.current_application_address
        assert xfer.asset_amount > 0

        existing = self.listings[key]
        self.listings[key] = ListingValue(
            bid=existing.bid,
            bidUnitaryPrice=existing.bidUnitaryPrice,
            bidder=existing.bidder,
            unitaryPrice=existing.unitaryPrice,
            deposited=existing.deposited + xfer.asset_amount,
        )

    @arc4.abimethod(name="setPrice")
    def set_price(self, asset: Asset, nonce: UInt64, unitary_price: UInt64) -> None:
        key = ListingKey(owner=Txn.sender, asset=asset.id, nonce=nonce)

        existing = self.listings[key]
        self.listings[key] = ListingValue(
            bid=existing.bid,
            bidUnitaryPrice=existing.bidUnitaryPrice,
            bidder=existing.bidder,
            deposited=existing.deposited,
            unitaryPrice=unitary_price,
        )

    @arc4.abimethod
    def buy(
        self,
        owner: Account,
        asset: Asset,
        nonce: UInt64,
        buy_pay: gtxn.PaymentTransaction,
        quantity: UInt64,
    ) -> None:
        key = ListingKey(owner=owner, asset=asset.id, nonce=nonce)

        listing = self.listings[key]

        amount_to_be_paid = self.quantity_price(quantity, listing.unitaryPrice, asset.decimals)

        assert buy_pay.sender == Txn.sender
        assert buy_pay.receiver == owner
        assert buy_pay.amount == amount_to_be_paid

        self.listings[key] = ListingValue(
            bid=listing.bid,
            bidUnitaryPrice=listing.bidUnitaryPrice,
            bidder=listing.bidder,
            unitaryPrice=listing.unitaryPrice,
            deposited=listing.deposited - quantity,
        )

        itxn.AssetTransfer(
            xfer_asset=asset, asset_receiver=Txn.sender, asset_amount=quantity
        ).submit()

    @arc4.abimethod
    def withdraw(self, asset: Asset, nonce: UInt64) -> None:
        key = ListingKey(owner=Txn.sender, asset=asset.id, nonce=nonce)

        listing = self.listings[key]
        if listing.bidder != Account():
            current_bid_deposit = self.quantity_price(
                listing.bid, listing.bidUnitaryPrice, asset.decimals
            )
            itxn.Payment(receiver=listing.bidder, amount=current_bid_deposit).submit()

        del self.listings[key]

        itxn.Payment(receiver=Txn.sender, amount=self.listings_box_mbr()).submit()

        itxn.AssetTransfer(
            xfer_asset=asset, asset_receiver=Txn.sender, asset_amount=listing.deposited
        ).submit()

    @arc4.abimethod
    def bid(
        self,
        owner: Account,
        asset: Asset,
        nonce: UInt64,
        bid_pay: gtxn.PaymentTransaction,
        quantity: UInt64,
        unitary_price: UInt64,
    ) -> None:
        key = ListingKey(owner=owner, asset=asset.id, nonce=nonce)

        listing = self.listings[key]
        if listing.bidder != Account():
            assert unitary_price > listing.bidUnitaryPrice

            current_bid_amount = self.quantity_price(
                listing.bid, listing.bidUnitaryPrice, asset.decimals
            )

            itxn.Payment(receiver=listing.bidder, amount=current_bid_amount).submit()

        amount_to_be_bid = self.quantity_price(quantity, unitary_price, asset.decimals)

        assert bid_pay.sender == Txn.sender
        assert bid_pay.receiver == Global.current_application_address
        assert bid_pay.amount == amount_to_be_bid

        self.listings[key] = ListingValue(
            deposited=listing.deposited,
            unitaryPrice=listing.unitaryPrice,
            bidder=Txn.sender,
            bid=quantity,
            bidUnitaryPrice=unitary_price,
        )

    @arc4.abimethod(name="acceptBid")
    def accept_bid(self, asset: Asset, nonce: UInt64) -> None:
        key = ListingKey(owner=Txn.sender, asset=asset.id, nonce=nonce)

        listing = self.listings[key]
        assert listing.bidder != Account()

        min_quantity = listing.deposited if listing.deposited < listing.bid else listing.bid

        best_bid_amount = self.quantity_price(
            min_quantity, listing.bidUnitaryPrice, asset.decimals
        )

        itxn.Payment(receiver=Txn.sender, amount=best_bid_amount).submit()

        itxn.AssetTransfer(
            xfer_asset=asset, asset_receiver=listing.bidder, asset_amount=min_quantity
        ).submit()

        self.listings[key] = ListingValue(
            bidder=listing.bidder,
            bidUnitaryPrice=listing.bidUnitaryPrice,
            unitaryPrice=listing.unitaryPrice,
            deposited=listing.deposited - min_quantity,
            bid=listing.bid - min_quantity,
        )
