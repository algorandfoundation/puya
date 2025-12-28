from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_contains_operator(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "contains", num_op_ups=1)
