from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from algopy import Asset, UInt64, gtxn
from algopy_testing import TestContext, blockchain_context

from .contract import AuctionContract


@pytest.fixture()
def context() -> Generator[TestContext[Any], None, None]:
    with blockchain_context() as ctx:
        yield ctx


@pytest.fixture()
def contract() -> AuctionContract:
    return AuctionContract()


def test_opt_into_asset(
    context: TestContext[Any], contract: AuctionContract, mocker: MagicMock
) -> None:
    # Arrange
    dummy_address = "A" * 58
    context.global_state.creator_address = dummy_address
    context.transaction_state.sender = dummy_address
    asset = Asset(123)
    mock_itxn_axfer = mocker.patch("algopy.itxn.AssetTransfer")

    # Act
    contract.opt_into_asset(asset)

    # Assert
    assert contract.asa.id == asset.id
    mock_itxn_axfer.assert_called_once()


def test_start_auction(
    context: TestContext[Any], contract: AuctionContract, mocker: MagicMock
) -> None:
    # Arrange
    dummy_address = "A" * 58
    dummy_app_address = "B" * 58
    context.global_state.creator_address = dummy_address
    context.global_state.current_application_address = dummy_app_address
    context.global_state.latest_timestamp = 1000
    context.transaction_state.sender = dummy_address
    axfer = mocker.Mock(spec=gtxn.AssetTransferTransaction)
    axfer.asset_receiver = dummy_app_address
    axfer.asset_amount = 1000

    # Act
    contract.start_auction(UInt64(100), UInt64(3600), axfer)

    # Assert
    assert contract.auction_end == context.global_state.latest_timestamp + 3600
    assert contract.previous_bid == 100
    assert contract.asa_amount == 1000


def test_bid(context: TestContext[Any], contract: AuctionContract, mocker: MagicMock) -> None:
    # Arrange
    dummy_address = "A" * 58
    context.global_state.creator_address = dummy_address
    context.global_state.latest_timestamp = 1000
    context.transaction_state.sender = dummy_address
    contract.auction_end = 2000
    contract.previous_bid = 100
    pay = mocker.Mock(spec=gtxn.PaymentTransaction)
    pay.sender = dummy_address
    pay.amount = 200

    # Act
    contract.bid(pay)

    # Assert
    assert contract.previous_bid == 200
    assert contract.previous_bidder == dummy_address
    assert contract.claimable_amount[dummy_address] == 200


def test_claim_bids(
    context: TestContext[Any], contract: AuctionContract, mocker: MagicMock
) -> None:
    # Arrange
    dummy_address = "A" * 58
    context.transaction_state.sender = dummy_address
    contract.claimable_amount[dummy_address] = 300
    contract.previous_bidder = dummy_address
    contract.previous_bid = 100
    mock_itxn_payment = mocker.patch("algopy.itxn.Payment")

    # Act
    contract.claim_bids()

    # Assert
    mock_itxn_payment.assert_called_once_with(
        amount=200,
        receiver=dummy_address,
    )
    assert contract.claimable_amount[dummy_address] == 100


def test_claim_asset(
    context: TestContext[Any], contract: AuctionContract, mocker: MagicMock
) -> None:
    # Arrange
    dummy_address = "A" * 58
    context.global_state.latest_timestamp = 2000
    contract.auction_end = 1000
    contract.previous_bidder = dummy_address
    contract.asa_amount = 1000
    asset = Asset(123)
    mock_itxn_axfer = mocker.patch("algopy.itxn.AssetTransfer")

    # Act
    contract.claim_asset(asset)

    # Assert
    mock_itxn_axfer.assert_called_once_with(
        xfer_asset=asset,
        asset_close_to=dummy_address,
        asset_receiver=dummy_address,
        asset_amount=1000,
    )


def test_delete_application(
    context: TestContext[Any], contract: AuctionContract, mocker: MagicMock
) -> None:
    # Arrange
    dummy_address = "A" * 58
    context.global_state.creator_address = dummy_address
    mock_itxn_payment = mocker.patch("algopy.itxn.Payment")

    # Act
    contract.delete_application()

    # Assert
    mock_itxn_payment.assert_called_once_with(
        receiver=dummy_address,
        close_remainder_to=dummy_address,
    )
