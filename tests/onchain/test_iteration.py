import pytest

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer

_EXPECTED_LOGS = [
    "test_forwards",
    "a",
    "b",
    "c",
    "test_reversed",
    "c",
    "b",
    "a",
    "test_forwards_with_forwards_index",
    "0=a",
    "1=b",
    "2=c",
    "test_forwards_with_reverse_index",
    "2=a",
    "1=b",
    "0=c",
    "test_reverse_with_forwards_index",
    "0=c",
    "1=b",
    "2=a",
    "test_reverse_with_reverse_index",
    "2=c",
    "1=b",
    "0=a",
    "test_empty",
    "test_break",
    "a",
    "test_tuple_target",
    "0=t",
]


@pytest.mark.parametrize(
    ("name", "num_op_ups"),
    [("tuple", 0), ("indexable", 1), ("urange", 1)],
    ids=["tuple", "indexable", "urange"],
)
def test_iteration(deployer_o: Deployer, name: str, num_op_ups: int) -> None:
    if num_op_ups:
        result = deployer_o.create_with_op_up(
            TEST_CASES_DIR / "iteration" / f"iterate_{name}.py",
            num_op_ups=num_op_ups,
        )
    else:
        result = deployer_o.create_bare(TEST_CASES_DIR / "iteration" / f"iterate_{name}.py")

    assert len(result.logs) == len(_EXPECTED_LOGS)
    logs_decoded = decode_logs(result.logs, len(_EXPECTED_LOGS) * "u")
    assert logs_decoded == _EXPECTED_LOGS
