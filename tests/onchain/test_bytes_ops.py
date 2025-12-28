from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_bytes_ops(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "bytes_ops")
