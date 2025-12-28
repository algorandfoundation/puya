import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_intrinsics_immediate_variants(deployer_o: Deployer) -> None:
    deployer_o.create_bare(
        TEST_CASES_DIR / "intrinsics" / "immediate_variants.py",
        args=[b""],
        static_fee=au.AlgoAmount.from_micro_algo(10_000),
    )
