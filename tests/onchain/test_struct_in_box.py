import algokit_utils as au

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer


def test_struct_in_box(deployer: Deployer, asset_a: int) -> None:
    client = deployer.create(EXAMPLES_DIR / "struct_in_box" / "contract.py").client

    # Fund the application (so it can have boxes)
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(10_000_000),
    )

    user_1 = {"id": 1, "name": "Bob", "asset": 0}
    user_2 = {"id": 2, "name": "Jane", "asset": 0}

    _call(client, "add_user", args=[user_1], box_key=1)
    _call(client, "add_user", args=[user_2], box_key=2)
    _call(client, "attach_asset_to_user", args=[user_1["id"], asset_a], box_key=1)

    user_1_result = _call(client, "get_user", args=[1], box_key=1)
    assert user_1_result.abi_return == {"name": "Bob", "id": 1, "asset": asset_a}

    user_2_result = _call(client, "get_user", args=[2], box_key=2)
    assert user_2_result.abi_return == {"name": "Jane", "id": 2, "asset": 0}


def _call(
    client: au.AppClient,
    method: str,
    *,
    args: list[object],
    box_key: int,
) -> au.SendAppTransactionResult[au.ABIValue]:
    return client.send.call(
        au.AppClientMethodCallParams(
            method=method,
            args=args,
            box_references=[box_key.to_bytes(8)],
        )
    )
