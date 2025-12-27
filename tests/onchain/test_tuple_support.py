from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_tuple_support(deployer: Deployer) -> None:
    response = deployer.create_bare((TEST_CASES_DIR / "tuple_support", "TupleSupport"))

    assert decode_logs(response.logs, "iuiiiuuuuu") == [
        306,
        "Hello, world!",
        0,
        2,
        1,
        "nanananana",
        "non_empty_tuple called",
        "not empty",
        "get_uint_with_side_effect called",
        "not empty2",
    ]


def test_tuple_comparisons(deployer: Deployer) -> None:
    response = deployer.create_bare((TEST_CASES_DIR / "tuple_support", "TupleComparisons"))
    expected_log_values = list(range(42, 48))

    assert (
        decode_logs(response.confirmation.logs, "i" * len(expected_log_values))
        == expected_log_values
    )
