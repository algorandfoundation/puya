import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


@pytest.mark.parametrize(
    ("file_name", "expected_init_log", "expected_method_log"),
    [
        (
            "base1",
            ["base1.__init__", "gp.__init__"],
            ["base1.method", "gp.method"],
        ),
        (
            "base2",
            ["base2.__init__", "gp.__init__"],
            ["base2.method", "gp.method"],
        ),
        (
            "derived",
            ["derived.__init__", "base1.__init__", "base2.__init__", "gp.__init__"],
            ["derived.method", "base1.method", "base2.method", "gp.method"],
        ),
    ],
)
def test_diamond_mro(
    deployer: Deployer,
    file_name: str,
    expected_init_log: list[str],
    expected_method_log: list[str],
) -> None:
    result = deployer.create(TEST_CASES_DIR / "diamond_mro" / f"{file_name}.py")
    client = result.client

    init_logs = decode_logs(result.logs, len(result.logs) * "u")
    assert init_logs == expected_init_log

    method_response = client.send.call(au.AppClientMethodCallParams(method="method"))
    method_logs_raw = method_response.confirmation.logs or []
    method_logs = decode_logs(method_logs_raw, "u" * len(method_logs_raw))
    assert method_logs == expected_method_log
