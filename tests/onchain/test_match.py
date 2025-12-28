from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_match(deployer_o: Deployer) -> None:
    response = deployer_o.create_bare(TEST_CASES_DIR / "match" / "contract.py", args=[b""])
    assert decode_logs(response.logs, 4 * "u") == [
        "Hello There biguint",
        "Hello bytes",
        "Hello one",
        "Hello True",
    ]
