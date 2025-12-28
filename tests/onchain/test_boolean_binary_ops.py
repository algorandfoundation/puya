from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_boolean_binary_ops(deployer_o: Deployer) -> None:
    response = deployer_o.create_with_op_up(TEST_CASES_DIR / "boolean_binary_ops", num_op_ups=1)

    logs = set(decode_logs(response.logs, "u" * 12))
    assert logs == {
        # AND
        "lhs_true_and_true",
        "rhs_true_and_true",
        "lhs_true_and_false",
        "rhs_true_and_false",
        "lhs_false_and_true",
        # "rhs_false_and_true",
        "lhs_false_and_false",
        # "rhs_false_and_false",
        # OR
        "lhs_true_or_true",
        # "rhs_true_or_true",
        "lhs_true_or_false",
        # "rhs_true_or_false",
        "lhs_false_or_true",
        "rhs_false_or_true",
        "lhs_false_or_false",
        "rhs_false_or_false",
    }
