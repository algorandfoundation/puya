import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_phi_congruence(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "phi_congruence.py").client

    def call(method: str, args: list[object]) -> object:
        return client.send.call(au.AppClientMethodCallParams(method=method, args=args)).abi_return

    assert call("test_cross_assignment", [42]) == 84
    assert call("test_cross_assignment", [0]) == 0
    assert call("test_triple_cycle", [10]) == 30
    assert call("test_redundant_phi", [0, 5]) == 0 | 5
    assert call("test_redundant_phi", [7, 5]) == 7 | 5
    assert call("test_replacement_chain", [0]) == 0
    assert call("test_replacement_chain", [42]) == 84

    with pytest.raises(au.LogicError, match="dynamic cost budget exceeded"):
        call("test_replacement_chain", [1])


def test_comparison_swaps(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "comparison_swaps.py")


def test_const_folding(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "const_folding.py").client
    client.send.call(au.AppClientMethodCallParams(method="entry"))


def test_getbyte_const_fold(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "getbyte_const_fold.py")


def test_negated_comparisons(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "negated_comparisons.py")


def test_partial_redundancy_elimination(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "partial_redundancy_elimination.py")


def test_replace3_const_fold(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "replace3_const_fold.py")


def test_wide_math_const_fold(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "wide_math_const_fold.py")
