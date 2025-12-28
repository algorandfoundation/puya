import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_avm_12(deployer: Deployer) -> None:
    client = deployer.create((TEST_CASES_DIR / "avm_12", "Contract")).client

    client.send.call(
        au.AppClientMethodCallParams(
            method="test_reject_version",
            static_fee=au.AlgoAmount.from_micro_algo(4000),
        )
    )
