import pytest
from algokit_utils import (
    get_algod_client,
    get_default_localnet_config,
    get_indexer_client,
    is_localnet,
)
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient


@pytest.fixture(scope="session")
def algod_client() -> AlgodClient:
    client = get_algod_client(get_default_localnet_config("algod"))

    # you can remove this assertion to test on other networks,
    # included here to prevent accidentally running against other networks
    assert is_localnet(client)
    return client


@pytest.fixture(scope="session")
def indexer_client() -> IndexerClient:
    return get_indexer_client(get_default_localnet_config("indexer"))
