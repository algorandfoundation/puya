from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_ssa(deployer: Deployer) -> None:
    response = deployer.create_bare(TEST_CASES_DIR / "ssa")

    assert decode_logs(response.logs, "i") == [102]
