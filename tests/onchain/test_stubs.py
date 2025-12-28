from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_bytes_stubs(deployer_o: Deployer) -> None:
    response = deployer_o.create_with_op_up(TEST_CASES_DIR / "stubs" / "bytes.py", num_op_ups=1)
    assert decode_logs(response.logs, "u") == ["one_to_seven called"]


def test_uint64_stubs(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "stubs" / "uint64.py", num_op_ups=1)


def test_string_stubs(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "stubs" / "string.py", num_op_ups=2)


def test_biguint_stubs(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(TEST_CASES_DIR / "stubs" / "biguint.py", num_op_ups=1)
