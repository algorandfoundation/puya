from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_arc4_uintn_comparisons(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(
        TEST_CASES_DIR / "arc4_numeric_comparisons" / "uint_n.py", num_op_ups=1
    )
