import random

import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


@pytest.fixture
def box_client(
    localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners
) -> au.AppClient:
    localnet = au.AlgorandClient(localnet_clients)
    localnet.account.set_signer_from_account(account)
    deployer = Deployer(localnet=localnet, account=account)

    client = deployer.create(TEST_CASES_DIR / "regression_tests" / "box_read_cache.py").client

    # Fund the app for box storage
    localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(10_000_000),
    )

    return client


def test_box_read_cache(box_client: au.AppClient) -> None:
    box_k = b"k"

    call = box_client.send.call
    response = call(
        au.AppClientMethodCallParams(
            method="repro",
            args=[],
            box_references=[box_k],
            note=random.randbytes(8),
        )
    )
    assert response.abi_return == (False, True, 0, 16)
