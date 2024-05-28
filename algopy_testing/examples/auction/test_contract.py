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
