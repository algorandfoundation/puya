from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_callsub(deployer: Deployer) -> None:
    response = deployer.create_bare(TEST_CASES_DIR / "callsub")

    assert decode_logs(response.confirmation.logs, "iii") == [42, 1, 2]
