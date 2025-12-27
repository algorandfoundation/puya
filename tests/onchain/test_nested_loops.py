from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_nested_loops(deployer: Deployer) -> None:
    response = deployer.create_with_op_up(TEST_CASES_DIR / "nested_loops", num_op_ups=15)

    x, y = decode_logs(response.confirmation.logs, "ii")
    assert x == 192
    assert y == 285
