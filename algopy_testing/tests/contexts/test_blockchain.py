from collections.abc import Generator
from typing import Any

import pytest
from algopy_testing.context import BlockchainContext, blockchain_context

from tests.artifacts.Auction.contract import AuctionContract


@pytest.fixture()
def context() -> Generator[BlockchainContext[Any], None, None]:
    with blockchain_context() as ctx:
        yield ctx


@pytest.fixture()
def contract() -> AuctionContract:
    return AuctionContract()


def test_opt_into_asset(context: BlockchainContext[Any], contract: AuctionContract) -> None:
    creator_address = "B" * 58
    context.set_global_state(creator_address=creator_address)
    asset = context.create_asset(1)

    context.set_custom_value("Txn.sender", creator_address)
    contract.opt_into_asset(asset)

    assert contract.asa.id == asset.id
