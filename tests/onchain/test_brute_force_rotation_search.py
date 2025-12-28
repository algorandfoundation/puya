import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


@pytest.mark.slow
def test_brute_force_rotation_search(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "stress_tests" / "brute_force_rotation_search.py")
