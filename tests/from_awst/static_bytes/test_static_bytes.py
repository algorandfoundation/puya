from pathlib import Path

import algokit_utils
import pytest
from algosdk.v2client.algod import AlgodClient

from tests import FROM_AWST_DIR
from tests.from_awst.util import compile_contract


@pytest.mark.localnet
def test_compile_and_run(
    algod_client: AlgodClient,
    account: algokit_utils.Account,
) -> None:
    test_dir = Path(__file__).parent
    out_dir = test_dir / "out"

    clients = compile_contract(
        algod_client=algod_client,
        account=account,
        awst_path=FROM_AWST_DIR / "static_bytes" / "module.awst.json",
        compilation_set={"tests/approvals/static-bytes.algo.ts::StaticBytesAlgo": out_dir},
    )

    app_client = clients["tests/approvals/static-bytes.algo.ts::StaticBytesAlgo"]

    app_client.create()

    res_receive_b32 = app_client.call(call_abi_method="receiveB32", b=b"\0" * 32)
    assert len(res_receive_b32.return_value) == 32

    app_client.call(call_abi_method="test")

    app_client.call(call_abi_method="testArray")
