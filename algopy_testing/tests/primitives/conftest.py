import typing
from pathlib import Path

import algokit_utils
import pytest
from algokit_utils import ApplicationClient, get_localnet_default_account
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient

from tests.common import AVMInvoker

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


def get_avm_result(
    create_avm_invoker: typing.Callable[[ApplicationClient], AVMInvoker],
    primitive_ops_client: ApplicationClient,
) -> AVMInvoker:
    return create_avm_invoker(primitive_ops_client)
