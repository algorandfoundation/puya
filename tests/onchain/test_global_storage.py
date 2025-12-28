from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer


def test_global_storage(deployer_o: Deployer) -> None:
    deployer_o.create_with_op_up(EXAMPLES_DIR / "global_state", num_op_ups=1)
