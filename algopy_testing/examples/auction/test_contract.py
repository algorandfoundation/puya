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
    assert len(context.get_transaction_group()) == 1
    assert contract.asa.id == asset.id
    inner_txn = context.get_last_submitted_inner_transaction()
    assert inner_txn.type == algopy.TransactionType.AssetTransfer
    assert (
        inner_txn.asset_receiver == context.default_application.address
    ), "Asset receiver does not match"
    assert inner_txn.xfer_asset == asset, "Transferred asset does not match"


def test_start_auction(
    context: AlgopyTestContext,
) -> None:
    # Arrange
    account = context.any_account()
    app_account = context.any_account()
    latest_timestamp = context.any_uint64(1, 1000)
    auction_price = context.any_uint64(1, 100)
    auction_duration = context.any_uint64(1000, 3600)
    axfer_txn = context.any_axfer_txn(
        group_index=0,
        asset_receiver=app_account,
        asset_amount=auction_price,
    )
    contract = AuctionContract()
    contract.asa_amount = auction_price
    context.patch_global_fields(
        creator_address=account,
        current_application_address=app_account,
        latest_timestamp=latest_timestamp,
    )
    context.patch_txn_fields(sender=account)

    # Act
    contract.start_auction(
        auction_price,
        auction_duration,
        axfer_txn,
    )

    # Assert
    assert contract.auction_end == latest_timestamp + auction_duration
    assert contract.previous_bid == auction_price
    assert contract.asa_amount == auction_price


def test_bid(context: AlgopyTestContext) -> None:
    # Arrange
    account = context.default_creator
    auction_end = context.any_uint64(min_value=int(time.time()) + 10_000)
    previous_bid = context.any_uint64(1, 100)
    pay_amount = context.any_uint64(100, 200)

    contract = AuctionContract()
    contract.auction_end = auction_end
    contract.previous_bid = previous_bid
    pay = context.any_pay_txn(group_index=0, sender=account, amount=pay_amount)

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
    claimable_amount = context.any_uint64(100, 300)
    contract.claimable_amount[account] = claimable_amount
    contract.previous_bidder = account
    previous_bid = context.any_uint64(1, 100)
    contract.previous_bid = previous_bid

    # Act
    contract.claim_bids()

    # Assert
    expected_payment = claimable_amount - previous_bid
    inner_transactions = context.get_last_inner_transaction_group()
    assert len(inner_transactions) == 1
    last_inner_txn = inner_transactions[0]
    assert last_inner_txn.type == algopy.TransactionType.Payment
    assert last_inner_txn.amount == expected_payment
    assert last_inner_txn.receiver == account
    assert contract.claimable_amount[account] == claimable_amount - expected_payment


def test_claim_asset(context: AlgopyTestContext) -> None:
    # Arrange
    account = context.any_account()
    latest_timestamp = context.any_uint64(1000, 2000)
    context.patch_global_fields(latest_timestamp=latest_timestamp)
    contract = AuctionContract()
    auction_end = context.any_uint64(1, 100)
    contract.auction_end = auction_end
    contract.previous_bidder = account
    asa_amount = context.any_uint64(1000, 2000)
    contract.asa_amount = asa_amount
    asset = context.any_asset()

    # Act
    contract.claim_asset(asset)

    # Assert
    inner_transactions = context.get_last_inner_transaction_group()
    assert len(inner_transactions) == 1
    last_inner_txn = inner_transactions[0]
    assert last_inner_txn.type == algopy.TransactionType.AssetTransfer
    assert last_inner_txn.xfer_asset == asset
    assert last_inner_txn.asset_close_to == account
    assert last_inner_txn.asset_receiver == account
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
    assert len(context.get_transaction_group()) == 1
    inner_transactions = context.get_last_submitted_inner_transaction()
    assert inner_transactions
    assert inner_transactions.type == algopy.TransactionType.Payment
    assert inner_transactions.receiver == account
    assert inner_transactions.close_remainder_to == account


@pytest.mark.usefixtures("context")
def test_clear_state_program() -> None:
    contract = AuctionContract()
    assert contract.clear_state_program()
