from pathlib import Path

import algokit_utils as au

from puya.compilation_artifacts import CompiledContract
from tests import AWST_DIR
from tests.utils import PuyaTestCase
from tests.utils.compile import arc56_from_compiled_contract, compile_from_test_case
from tests.utils.deployer import Deployer


def test_itxn_compose(
    localnet: au.AlgorandClient, account: au.AddressWithSigners, deployer: Deployer, tmp_path: Path
) -> None:
    test_case = PuyaTestCase(AWST_DIR / "itxn_compose")
    contracts = {
        artifact.id.removeprefix(
            "tests/approvals/itxn-compose.algo.ts::"
        ): arc56_from_compiled_contract(artifact)
        for artifact in compile_from_test_case(test_case, out_dir=tmp_path).teal
        if isinstance(artifact, CompiledContract)
    }
    app_client_verify = deployer.create(contracts["VerifierContract"]).client
    app_client_itxn = deployer.create(contracts["ItxnComposeAlgo"]).client

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
