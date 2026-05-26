import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_phi_congruence(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "phi_congruence.py").client

    def call(method: str, args: list[object]) -> object:
        return client.send.call(au.AppClientMethodCallParams(method=method, args=args)).abi_return

    assert call("call_test_cross_assignment", [42]) == 84
    assert call("call_test_cross_assignment", [0]) == 0
    assert call("call_test_triple_cycle", [10]) == 30
    assert call("call_test_redundant_phi", [0, 5]) == 0 | 5
    assert call("call_test_redundant_phi", [7, 5]) == 7 | 5
    assert call("call_test_replacement_chain", [0]) == 0
    assert call("call_test_replacement_chain", [42]) == 84

    with pytest.raises(au.LogicError, match="dynamic cost budget exceeded"):
        call("call_test_replacement_chain", [1])
