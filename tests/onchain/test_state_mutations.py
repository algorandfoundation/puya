import random

import algokit_utils as au
from algokit_common import public_key_from_address

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_state_mutations(deployer: Deployer) -> None:
    client = deployer.create(TEST_CASES_DIR / "state_mutations").client

    # Fund app for boxes
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(200_000),
    )

    map_key = b"map" + public_key_from_address(deployer.account.addr)

    def call(method: str) -> au.SendAppTransactionResult[au.ABIValue]:
        return client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                box_references=[b"box", map_key],
                note=random.randbytes(8),
            )
        )

    client.send.bare.call(
        au.AppClientBareCallParams(box_references=[b"box", map_key]),
        on_complete=au.OnApplicationComplete.OptIn,
    )

    response = call("get")
    assert response.abi_return == []

    # append
    call("append")
    response = call("get")
    assert response.abi_return == [(1, "baz")]

    # modify
    call("modify")
    response = call("get")
    assert response.abi_return == [(1, "modified")]

    # append again
    call("append")
    response = call("get")
    assert response.abi_return == [(1, "modified"), (1, "baz")]
