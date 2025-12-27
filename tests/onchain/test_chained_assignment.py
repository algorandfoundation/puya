from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_chained_assignment(deployer: Deployer) -> None:
    response = deployer.create_bare(TEST_CASES_DIR / "chained_assignment")

    assert decode_logs(response.confirmation.logs, "u") == ["Hello, world! 👋"]
