from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_string_ops(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "string_ops", num_op_ups=4)
