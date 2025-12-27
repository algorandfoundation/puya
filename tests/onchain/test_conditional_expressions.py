import collections

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_conditional_expressions(deployer: Deployer) -> None:
    response = deployer.create_bare(TEST_CASES_DIR / "conditional_expressions" / "contract.py")

    logs = decode_logs(response.logs, ("u" * 6) + "i")
    counts = collections.Counter(logs[:-1])
    assert counts == {
        "expensive_op": 3,
        "side_effecting_op": 3,
    }
    assert logs[-1] == 19


def test_literal_conditional_expressions(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "conditional_expressions" / "literals.py")
