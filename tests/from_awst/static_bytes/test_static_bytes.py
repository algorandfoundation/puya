from pathlib import Path

import algokit_utils as au
import pytest

from tests import FROM_AWST_DIR
from tests.from_awst.util import compile_contract_and_clients


@pytest.mark.localnet
def test_compile_and_run(
    localnet: au.AlgorandClient,
    account: au.AddressWithSigners,
) -> None:
    test_dir = Path(__file__).parent
    out_dir = test_dir / "out"

    clients = compile_contract_and_clients(
        algorand=localnet,
        account=account,
        awst_path=FROM_AWST_DIR / "static_bytes" / "module.awst.json",
        compilation_set={"tests/approvals/static-bytes.algo.ts::StaticBytesAlgo": out_dir},
    )

    app_client_factory = clients["tests/approvals/static-bytes.algo.ts::StaticBytesAlgo"]

    app_client, _ = app_client_factory.send.bare.create()

    res_receive_b32 = app_client.send.call(
        au.AppClientMethodCallParams(
            method="receiveB32",
            args=[bytes(32)],
        )
    )
    assert isinstance(res_receive_b32.abi_return, bytes)
    assert len(res_receive_b32.abi_return) == 32

    app_client.send.call(au.AppClientMethodCallParams(method="test"))
    app_client.send.call(au.AppClientMethodCallParams(method="testArray"))
