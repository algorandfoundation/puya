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
        awst_path=FROM_AWST_DIR / "itxn_compose" / "module.awst.json",
        compilation_set={
            "tests/approvals/itxn-compose.algo.ts::ItxnComposeAlgo": out_dir,
            "tests/approvals/itxn-compose.algo.ts::VerifierContract": out_dir,
        },
    )
    app_client_verify_factory = clients["tests/approvals/itxn-compose.algo.ts::VerifierContract"]
    app_client_itxn_factory = clients["tests/approvals/itxn-compose.algo.ts::ItxnComposeAlgo"]

    app_client_verify, _ = app_client_verify_factory.send.bare.create()
    app_client_itxn, _ = app_client_itxn_factory.send.bare.create()

    localnet.account.ensure_funded(
        account_to_fund=app_client_itxn.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_algo(5),
    )

    addresses = []
    for _ in range(3):
        a = localnet.account.random()
        localnet.account.ensure_funded(
            account_to_fund=a.addr,
            dispenser_account=account,
            min_spending_balance=au.AlgoAmount.from_algo(1),
        )
        addresses.append(a.addr)

    pay = localnet.create_transaction.payment(
        au.PaymentParams(
            sender=account.addr,
            receiver=app_client_itxn.app_address,
            amount=au.AlgoAmount.from_micro_algo(9_000),
        )
    )

    app_client_itxn.send.call(
        au.AppClientMethodCallParams(
            method="distribute",
            args=[
                addresses,
                pay,
                app_client_verify.app_id,
            ],
            max_fee=au.AlgoAmount.from_micro_algo(6_000),
        ),
        send_params=au.SendParams(
            populate_app_call_resources=True, cover_app_call_inner_transaction_fees=True
        ),
    )

    app_client_itxn.send.call(
        au.AppClientMethodCallParams(
            method="conditionalBegin",
            args=[4],
            max_fee=au.AlgoAmount.from_micro_algo(6_000),
        ),
        send_params=au.SendParams(cover_app_call_inner_transaction_fees=True),
    )
