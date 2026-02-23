from pathlib import Path

import algokit_utils as au
import pytest

from tests import FROM_AWST_DIR
from tests.from_awst.util import compile_contract_and_clients


@pytest.mark.filterwarnings("ignore:replaced by StageInnerTransactions")
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
        awst_path=FROM_AWST_DIR / "emit" / "module.awst.json",
        compilation_set={
            "tests/approvals/arc-28-events.algo.ts::EventEmitter": out_dir,
        },
    )
    app_client_factory = clients["tests/approvals/arc-28-events.algo.ts::EventEmitter"]

    app_client, _ = app_client_factory.send.bare.create()

    app_client.send.call(
        au.AppClientMethodCallParams(
            method="emitSwapped",
            args=[42, 64],
            max_fee=au.AlgoAmount.from_micro_algo(6_000),
        ),
        send_params=au.SendParams(
            populate_app_call_resources=True, cover_app_call_inner_transaction_fees=True
        ),
    )

    app_client.send.call(
        au.AppClientMethodCallParams(
            method="emitCustom",
            args=["hello world", True],
            max_fee=au.AlgoAmount.from_micro_algo(6_000),
        ),
        send_params=au.SendParams(cover_app_call_inner_transaction_fees=True),
    )

    app_client.send.call(
        au.AppClientMethodCallParams(
            method="emitDynamicBytes",
            args=[b"hello", b"world"],
            max_fee=au.AlgoAmount.from_micro_algo(6_000),
        ),
        send_params=au.SendParams(cover_app_call_inner_transaction_fees=True),
    )
