import algokit_utils as au
import pytest

from tests import EXAMPLES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_calculator(deployer: Deployer) -> None:
    path = EXAMPLES_DIR / "calculator"
    add, sub, mul, div = 1, 2, 3, 4

    def call(op: int, a: int, b: int) -> list[str | bytes | int]:
        response = deployer.create_bare(path, args=[arg.to_bytes() for arg in (op, a, b)])
        return decode_logs(response.confirmation.logs, "iiu")

    assert call(add, 1, 2) == [1, 2, "1 + 2 = 3"]
    assert call(sub, 45, 2) == [45, 2, "45 - 2 = 43"]
    assert call(mul, 42, 42) == [42, 42, "42 * 42 = 1764"]
    assert call(div, 8, 2) == [8, 2, "8 // 2 = 4"]

    with pytest.raises(au.LogicError):
        deployer.create_bare(path)

    # invalid operation should fail
    with pytest.raises(au.LogicError):
        call(9, 20, 8)
