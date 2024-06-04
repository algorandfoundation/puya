from collections.abc import Generator
from typing import Any

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

from .contract import AuctionContract


@pytest.fixture()
def context() -> Generator[AlgopyTestContext[Any], None, None]:
    with algopy_testing_context(AuctionContract) as ctx:
        yield ctx
        ctx.reset()


def test_opt_into_asset(context: AlgopyTestContext[Any]) -> None:
    # Arrange
    account = context.any_account(
        auth_address=context.any_account(), balance=context.any_uint64(1, 1000)
    )
    application_address = context.any_account()
    asset = context.any_asset()

    context.patch_global_fields(
        creator_address=account, current_application_address=application_address
    )
    context.patch_txn_fields(sender=account)

    contract = AuctionContract()

    # Act
    contract.opt_into_asset(asset)

    # Assert
    assert asset.id
    assert contract.asa.id == asset.id
    assert len(context.inner_transactions) == 1
    assert isinstance(context.inner_transactions[0], algopy.itxn.AssetTransfer)
    assert context.inner_transactions[0] == algopy.itxn.AssetTransfer(
        asset_receiver=application_address,
        xfer_asset=asset,
    )


def test_start_auction(
    context: AlgopyTestContext[Any],
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


def test_bid(context: AlgopyTestContext[Any]) -> None:
    # Arrange
    account = context.any_account()
    auction_end = context.any_uint64(1000, 2000)
    previous_bid = context.any_uint64(1, 100)
    pay_amount = context.any_uint64(100, 200)
    context.patch_global_fields(
        creator_address=account, latest_timestamp=context.any_uint64(1000, 1000)
    )
    context.patch_txn_fields(sender=account)

    contract = AuctionContract()
    contract.auction_end = auction_end
    contract.previous_bid = previous_bid
    pay = context.any_pay_txn(sender=account, amount=pay_amount)

    # Act
    contract.bid(pay)

    # Assert
    assert contract.previous_bid == pay_amount
    assert contract.previous_bidder == account
    assert contract.claimable_amount[account] == pay_amount


def test_claim_bids(
    context: AlgopyTestContext[Any],
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
    assert len(context.inner_transactions) == 1
    assert isinstance(context.inner_transactions[0], algopy.itxn.Payment)
    assert context.inner_transactions[0] == algopy.itxn.Payment(
        amount=expected_payment,
        receiver=account,
    )
    assert contract.claimable_amount[account] == claimable_amount - expected_payment


def test_claim_asset(context: AlgopyTestContext[Any]) -> None:
    # Arrange
    account = context.any_account()
    latest_timestamp = context.any_uint64(1000, 2000)
    context.patch_global_fields(latest_timestamp=latest_timestamp)
    contract = AuctionContract()
    auction_end = context.any_uint64(1, 100)
    contract.auction_end = auction_end
    contract.previous_bidder = account
    asa_amount = context.any_uint64(1000, 1000)
    contract.asa_amount = asa_amount
    asset = context.any_asset()

    # Act
    contract.claim_asset(asset)

    # Assert
    assert len(context.inner_transactions) == 1
    assert isinstance(context.inner_transactions[0], algopy.itxn.AssetTransfer)
    assert context.inner_transactions[0] == algopy.itxn.AssetTransfer(
        xfer_asset=asset,
        asset_close_to=account,
        asset_receiver=account,
        asset_amount=asa_amount,
    )


def test_delete_application(
    context: AlgopyTestContext[Any],
) -> None:
    # Arrange
    account = context.any_account()
    context.patch_global_fields(creator_address=account)

    # Act
    contract = AuctionContract()
    contract.delete_application()

    # Assert
    assert len(context.inner_transactions) == 1
    assert isinstance(context.inner_transactions[0], algopy.itxn.Payment)
    assert context.inner_transactions[0] == algopy.itxn.Payment(
        receiver=account,
        close_remainder_to=account,
    )


def test_clear_state_program() -> None:
    contract = AuctionContract()
    assert contract.clear_state_program()
