from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_too_many_permutations(deployer_o: Deployer) -> None:
    deployer_o.create_bare(
        TEST_CASES_DIR / "too_many_permutations", args=[b"\1", b"\2", b"\3", b"\4"]
    )
