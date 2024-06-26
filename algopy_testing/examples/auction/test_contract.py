import time
from collections.abc import Generator

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

from .contract import AuctionContract


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx
        ctx.reset()


def test_opt_into_asset(context: AlgopyTestContext) -> None:
    # Arrange
    asset = context.any_asset()
    contract = AuctionContract()

    # Act
    contract.opt_into_asset(asset)

    # Assert
    assert contract.asa.id == asset.id
    inner_txn = context.last_submitted_itxn.asset_transfer
    assert (
        inner_txn.asset_receiver == context.default_application.address
    ), "Asset receiver does not match"
    assert inner_txn.xfer_asset == asset, "Transferred asset does not match"


def test_start_auction(
    context: AlgopyTestContext,
) -> None:
    # Arrange
    latest_timestamp = context.any_uint64(1, 1000)
    starting_price = context.any_uint64()
    auction_duration = context.any_uint64(100, 1000)
    axfer_txn = context.any_asset_transfer_transaction(
        asset_receiver=context.default_application.address,
        asset_amount=starting_price,
    )
    contract = AuctionContract()
    contract.asa_amount = starting_price
    context.patch_global_fields(
        latest_timestamp=latest_timestamp,
    )
    context.patch_txn_fields(sender=context.default_creator)

    # Act
    contract.start_auction(
        starting_price,
        auction_duration,
        axfer_txn,
    )

    # Assert
    assert contract.auction_end == latest_timestamp + auction_duration
    assert contract.previous_bid == starting_price
    assert contract.asa_amount == starting_price


def test_bid(context: AlgopyTestContext) -> None:
    # Arrange
    account = context.default_creator
    auction_end = context.any_uint64(min_value=int(time.time()) + 10_000)
    previous_bid = context.any_uint64(1, 100)
    pay_amount = context.any_uint64()

    contract = AuctionContract()
    contract.auction_end = auction_end
    contract.previous_bid = previous_bid
    pay = context.any_payment_transaction(sender=account, amount=pay_amount)

    # Act
    contract.bid(pay=pay)

    # Assert
    assert contract.previous_bid == pay_amount
    assert contract.previous_bidder == account
    assert contract.claimable_amount[account] == pay_amount


def test_claim_bids(
    context: AlgopyTestContext,
) -> None:
    # Arrange
    account = context.any_account()
    context.patch_txn_fields(sender=account)
    contract = AuctionContract()
    claimable_amount = context.any_uint64()
    contract.claimable_amount[account] = claimable_amount
    contract.previous_bidder = account
    previous_bid = context.any_uint64(max_value=int(claimable_amount))
    contract.previous_bid = previous_bid

    # Act
    contract.claim_bids()

    # Assert
    expected_payment = claimable_amount - previous_bid
    last_inner_txn = context.last_submitted_itxn.payment

    assert last_inner_txn.amount == expected_payment
    assert last_inner_txn.receiver == account
    assert contract.claimable_amount[account] == claimable_amount - expected_payment


def test_claim_asset(context: AlgopyTestContext) -> None:
    # Arrange
    context.patch_global_fields(latest_timestamp=context.any_uint64())
    contract = AuctionContract()
    contract.auction_end = context.any_uint64(1, 100)
    contract.previous_bidder = context.default_creator
    asa_amount = context.any_uint64(1000, 2000)
    contract.asa_amount = asa_amount
    asset = context.any_asset()

    # Act
    contract.claim_asset(asset)

    # Assert
    last_inner_txn = context.last_submitted_itxn.asset_transfer
    assert last_inner_txn.xfer_asset == asset
    assert last_inner_txn.asset_close_to == context.default_creator
    assert last_inner_txn.asset_receiver == context.default_creator
    assert last_inner_txn.asset_amount == asa_amount


def test_delete_application(
    context: AlgopyTestContext,
) -> None:
    # Arrange
    account = context.any_account()
    context.patch_global_fields(creator_address=account)

    # Act
    contract = AuctionContract()
    contract.delete_application()

    # Assert
    inner_transactions = context.last_submitted_itxn.payment
    assert inner_transactions
    assert inner_transactions.type == algopy.TransactionType.Payment
    assert inner_transactions.receiver == account
    assert inner_transactions.close_remainder_to == account


@pytest.mark.usefixtures("context")
def test_clear_state_program() -> None:
    contract = AuctionContract()
    assert contract.clear_state_program()
