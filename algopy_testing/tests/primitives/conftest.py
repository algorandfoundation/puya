import random
import typing
from pathlib import Path

import algokit_utils
import pytest
from algokit_utils import ApplicationClient, get_localnet_default_account
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

ARTIFACTS_DIR = Path(__file__).parent / ".." / "artifacts"
APP_SPEC = ARTIFACTS_DIR / "PrimitiveOps" / "data" / "PrimitiveOpsContract.arc32.json"


@pytest.fixture(scope="session")
def primitive_ops_client(
    algod_client: AlgodClient, indexer_client: IndexerClient
) -> ApplicationClient:
    config.configure(
        debug=True,
    )

    client = ApplicationClient(
        algod_client,
        APP_SPEC,
        creator=get_localnet_default_account(algod_client),
        indexer_client=indexer_client,
    )

    client.deploy(
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
        on_update=algokit_utils.OnUpdate.AppendApp,
    )
    return client


class AVMInvoker(typing.Protocol):

    def __call__(self, method: str, **kwargs: typing.Any) -> object: ...


@pytest.fixture(scope="module")
def get_avm_result(primitive_ops_client: ApplicationClient) -> AVMInvoker:

    def wrapped(method: str, **kwargs: typing.Any) -> object:
        result = primitive_ops_client.call(
            method,
            transaction_parameters={
                # random note avoids duplicate txn if tests are running concurrently
                "note": random.randbytes(8),  # noqa: S311
            },
            **kwargs,
        ).return_value
        if isinstance(result, list) and all(isinstance(i, int) for i in result):
            result = bytes(result)
        return result

    return wrapped
