from pathlib import Path

import algokit_utils
import algosdk
import pytest
from algosdk.atomic_transaction_composer import TransactionWithSigner
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
        awst_path=FROM_AWST_DIR / "itxn_compose" / "module.awst.json",
        compilation_set={
            "tests/approvals/itxn-compose.algo.ts::ItxnComposeAlgo": out_dir,
            "tests/approvals/itxn-compose.algo.ts::VerifierContract": out_dir,
        },
    )
    app_client_verify = clients["tests/approvals/itxn-compose.algo.ts::VerifierContract"]
    app_client_itxn = clients["tests/approvals/itxn-compose.algo.ts::ItxnComposeAlgo"]

    app_client_verify.create()
    app_client_itxn.create()

    algokit_utils.ensure_funded(
        algod_client,
        algokit_utils.EnsureBalanceParameters(
            account_to_fund=app_client_itxn.app_address,
            min_spending_balance_micro_algos=5_000_000,
        ),
    )
    accounts = [
        algokit_utils.get_account(algod_client, name="A", fund_with_algos=1000),
        algokit_utils.get_account(algod_client, name="B", fund_with_algos=1000),
        algokit_utils.get_account(algod_client, name="C", fund_with_algos=1000),
    ]
    addresses = [a.address for a in accounts]

    pay = TransactionWithSigner(
        txn=algosdk.transaction.PaymentTxn(
            sender=account.address,
            receiver=app_client_itxn.app_address,
            amt=9_000,
            sp=algod_client.suggested_params(),
        ),
        signer=account.signer,
    )

    sp = algod_client.suggested_params()
    sp.fee = 1000

    app_client_itxn.call(
        call_abi_method="distribute",
        addresses=addresses,
        funds=pay,
        verifier=app_client_verify.app_id,
        transaction_parameters=algokit_utils.OnCompleteCallParameters(
            foreign_apps=[app_client_verify.app_id], accounts=addresses, suggested_params=sp
        ),
    )

    app_client_itxn.call(
        call_abi_method="conditionalBegin",
        count=4,
        transaction_parameters=algokit_utils.OnCompleteCallParameters(suggested_params=sp),
    )
