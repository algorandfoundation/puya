from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_scratch_slots(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "scratch_slots" / "contract.py")


def test_scratch_slots_inheritance(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "scratch_slots" / "contract2.py")
