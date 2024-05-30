from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from algopy import UInt64, gtxn
from algopy_testing import TestContext, blockchain_context

from .contract import AuctionContract


@pytest.fixture()
def context() -> Generator[TestContext[Any], None, None]:
    with blockchain_context() as ctx:
        yield ctx


def test_opt_into_asset(
    context: TestContext[Any],
) -> None:
    # Arrange
    dummy_account = context.any_account()
    context.set_global_fields(
        {
            "creator_address": dummy_account,
            "current_application_address": dummy_account,
        }
    )
    dummy_asset = context.any_asset()

    # Act
    contract = AuctionContract()
    contract.opt_into_asset(dummy_asset)

    # Assert
    assert contract.asa.id == dummy_asset.id
    assert len(context.inner_transactions) == 1


def test_start_auction(context: TestContext[Any], mocker: MagicMock) -> None:
    # Arrange
    dummy_account = context.any_account()
    dummy_app_account = context.any_account()
    context.set_global_fields(
        {
            "creator_address": dummy_account,
            "current_application_address": dummy_app_account,
            "latest_timestamp": context.any_uint64(1000, 1000),
        }
    )
    context.set_txn_fields({"sender": dummy_account})
    axfer = mocker.Mock(spec=gtxn.AssetTransferTransaction)
    axfer.asset_receiver = dummy_app_account
    axfer.asset_amount = 1000

    # Act
    contract = AuctionContract()
    contract.start_auction(
        UInt64(context.any_uint64(100, 100).value),
        UInt64(context.any_uint64(3600, 3600).value),
        axfer,
    )

    # Assert
    assert context.global_fields.latest_timestamp
    assert contract.auction_end == context.global_fields.latest_timestamp + 3600
    assert contract.previous_bid == 100
    assert contract.asa_amount == 1000


def test_bid(context: TestContext[Any], mocker: MagicMock) -> None:
    # Arrange
    dummy_account = context.any_account()
    context.set_global_fields(
        {"creator_address": dummy_account, "latest_timestamp": context.any_uint64(1000, 1000)}
    )
    contract = AuctionContract()
    contract.auction_end = UInt64(context.any_uint64(2000, 2000).value)
    contract.previous_bid = UInt64(context.any_uint64(100, 100).value)
    pay = mocker.Mock(spec=gtxn.PaymentTransaction)
    pay.sender = dummy_account
    random_amount = context.any_uint64(200, 200)
    pay.amount = UInt64(random_amount.value)

    # Act
    contract.bid(pay)

    # Assert
    assert contract.previous_bid == 200
    assert contract.previous_bidder == dummy_account


def test_claim_bids(
    context: TestContext[Any],
) -> None:
    # Arrange
    dummy_account = context.any_account()
    context.set_txn_fields({"sender": dummy_account})
    contract = AuctionContract()
    contract.claimable_amount[dummy_account.address] = UInt64(context.any_uint64(300, 300).value)
    contract.previous_bidder = dummy_account
    contract.previous_bid = UInt64(context.any_uint64(100, 100).value)

    # Act
    contract.claim_bids()

    # Assert
    assert len(context.inner_transactions) > 1
    assert contract.claimable_amount[dummy_account.address] == 100


def test_claim_asset(context: TestContext[Any]) -> None:
    # Arrange
    dummy_account = context.any_account()
    context.set_global_fields({"latest_timestamp": context.any_uint64(2000, 2000)})
    contract = AuctionContract()
    contract.auction_end = context.any_uint64(1000, 1000)
    contract.previous_bidder = dummy_account
    contract.asa_amount = context.any_uint64(1000, 1000)
    asset = context.any_asset()

    # Act
    contract.claim_asset(asset)

    # Assert
    assert len(context.inner_transactions) > 1


def test_delete_application(context: TestContext[Any], mocker: MagicMock) -> None:
    # Arrange
    dummy_account = context.any_account()
    context.set_global_fields({"creator_address": dummy_account})
    mock_itxn_payment = mocker.patch("algopy.itxn.Payment")

    # Act
    contract = AuctionContract()
    contract.delete_application()

    # Assert
    mock_itxn_payment.assert_called_once_with(
        receiver=dummy_account,
        close_remainder_to=dummy_account,
    )
