import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_application(deployer_o: Deployer) -> None:
    client = deployer_o.create_bare(TEST_CASES_DIR / "application").client

    client.send.bare.call(au.AppClientBareCallParams(args=[b"validate"]))
