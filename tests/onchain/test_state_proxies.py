import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_CONTRACT_PATH = TEST_CASES_DIR / "state_proxies" / "contract.py"


def test_state_proxies(deployer: Deployer) -> None:
    result = deployer.create(
        _CONTRACT_PATH,
        on_complete=au.OnApplicationComplete.OptIn,
    )
    client = result.client
    account = deployer.account

    global_state = client.get_global_state()
    assert global_state["g1"].value == 1
    assert global_state["g2"].value == 0
    assert global_state["funky"].value == 123

    local_state = client.get_local_state(account.addr)
    assert local_state["l1"].value == 2
    assert local_state["l2"].value == 3

    # Fund app for boxes
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(100_000),
    )

    # Call clear with box reference
    client.send.call(au.AppClientMethodCallParams(method="clear"))

    # Test order_of_eval_global
    response = client.send.call(au.AppClientMethodCallParams(method="order_of_eval_global"))
    assert response.confirmation.logs == [b"default"]

    # Test order_of_eval_local
    response = client.send.call(au.AppClientMethodCallParams(method="order_of_eval_local"))
    assert response.confirmation.logs == [b"account", b"default"]

    # Test order_of_eval_box
    response = client.send.call(au.AppClientMethodCallParams(method="order_of_eval_box"))
    assert response.confirmation.logs == [b"key", b"default"]
    assert response.confirmation.logs == [b"key", b"default"]
