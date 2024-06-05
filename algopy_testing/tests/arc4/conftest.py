from pathlib import Path

import pytest
from algosdk.v2client.algod import AlgodClient

from tests.common import AVMInvoker, create_avm_invoker

ARTIFACTS_DIR = Path(__file__).parent / ".." / "artifacts"
APP_SPEC = ARTIFACTS_DIR / "Arc4PrimitiveOps" / "data" / "Arc4PrimitiveOpsContract.arc32.json"


@pytest.fixture(scope="module")
def get_avm_result(algod_client: AlgodClient) -> AVMInvoker:
    return create_avm_invoker(APP_SPEC, algod_client)
