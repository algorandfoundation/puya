from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_with_reentrancy(deployer: Deployer) -> None:
    response = deployer.create_bare(TEST_CASES_DIR / "with_reentrancy")

    assert decode_logs(response.logs, "iuuuuuu") == [
        5,
        "silly3 = 8",
        "silly2 = 8",
        "silly = 6",
        "silly3 = 5",
        "silly2 = 5",
        "silly = 3",
    ]
