import algokit_utils as au
from algokit_common import public_key_from_address

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_DYNAMIC_ITXN_GROUP_DIR = TEST_CASES_DIR / "dynamic_itxn_group"


def test_dynamic_itxn_group(deployer: Deployer) -> None:
    algorand = deployer.localnet

    # Create both apps
    client = deployer.create(_DYNAMIC_ITXN_GROUP_DIR / "contract.py").client
    verifier_client = deployer.create(_DYNAMIC_ITXN_GROUP_DIR / "verifier.py").client

    # Fund the main app
    algorand.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(400_000),
    )

    # Create 4 funded test accounts
    test_accounts = []
    for _ in range(4):
        acc = algorand.account.random()
        algorand.account.ensure_funded(
            account_to_fund=acc.addr,
            dispenser_account=deployer.account,
            min_spending_balance=au.AlgoAmount.from_micro_algo(400_000),
        )
        test_accounts.append(acc)

    # Get public keys for accounts
    addresses = [public_key_from_address(a.addr) for a in test_accounts]

    def call(method: str) -> None:
        pay = algorand.create_transaction.payment(
            au.PaymentParams(
                sender=deployer.account.addr,
                receiver=client.app_address,
                amount=au.AlgoAmount.from_micro_algo(900_000),
                note=b"minimum balance to optin to an asset",
            )
        )
        client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                args=[addresses, pay, verifier_client.app_id],
                static_fee=au.AlgoAmount.from_micro_algo(100_000),
            )
        )

    call("test_firstly")
    call("test_looply")
    call("test_firstly_abi_call")
    call("test_looply_abi_call")
