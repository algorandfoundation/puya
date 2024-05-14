import random
import typing

import pytest
from algokit_utils import (
    ApplicationClient,
    get_algod_client,
    get_default_localnet_config,
    get_indexer_client,
    is_localnet,
)
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from tests.common import AVMInvoker


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


@pytest.fixture(scope="module")
def create_avm_invoker() -> typing.Callable[[ApplicationClient], AVMInvoker]:
    def _invoke_avm(client: ApplicationClient) -> AVMInvoker:
        def invoke(method: str, **kwargs: typing.Any) -> object:
            sp = client.algod_client.suggested_params()
            sp.fee = kwargs.pop("custom_fee", sp.fee)
            result = client.call(
                method,
                transaction_parameters={
                    # random note avoids duplicate txn if tests are running concurrently
                    "note": random.randbytes(8),  # noqa: S311
                    "suggested_params": sp,
                },
                **kwargs,
            ).return_value
            if isinstance(result, list) and all(isinstance(i, int) for i in result):
                result = bytes(result)
            return result

        return invoke

    return _invoke_avm
