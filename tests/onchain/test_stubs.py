from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_uint64_stubs(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "stubs" / "uint64.py", num_op_ups=1)


def test_string_stubs(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "stubs" / "string.py", num_op_ups=2)


def test_biguint_stubs(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "stubs" / "biguint.py", num_op_ups=1)
