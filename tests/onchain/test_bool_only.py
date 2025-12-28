import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_bool_only(deployer: Deployer) -> None:
    client = deployer.create((TEST_CASES_DIR / "regression_tests", "BoolOnly")).client

    response = client.send.call(
        au.AppClientMethodCallParams(method="set_0_convert", args=[b"\x00"])
    )
    assert response.abi_return == bytes([2**7])

    response = client.send.call(
        au.AppClientMethodCallParams(method="set_0_compare", args=[b"\x00"])
    )
    assert response.abi_return == bytes([2**7])

    # Fund app to meet minimum balance requirements
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(100_000),
    )

    # 4 inner transactions = 4000 fee
    client.send.call(
        au.AppClientMethodCallParams(
            method="bool_only_properties",
            static_fee=au.AlgoAmount.from_micro_algo(4000),
        )
    )
