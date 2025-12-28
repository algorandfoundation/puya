from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_unssa(deployer_o: Deployer) -> None:
    response = deployer_o.create_with_op_up(TEST_CASES_DIR / "unssa", num_op_ups=1)

    result1, result2 = decode_logs(response.logs, "ii")
    assert result1 == 2
    assert result2 == 1
