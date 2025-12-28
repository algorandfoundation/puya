import pytest

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


@pytest.mark.parametrize(
    ("args", "expected_logs"),
    [
        ([], []),
        ([1], [1]),
        ([1, 2], []),
        ([1, 2, 3], [3]),
    ],
)
def test_control_op_simplification(
    deployer_o: Deployer, args: list[int], expected_logs: list[int]
) -> None:
    result = deployer_o.create_bare(TEST_CASES_DIR / "control_op_simplification", args=args)
    assert decode_logs(result.logs, "i" * len(expected_logs)) == expected_logs
