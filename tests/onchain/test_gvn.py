import random

import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_btoi_itob_vn(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "btoi_itob_vn.py")


def test_same_vn_binary_ops(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "same_vn_binary_ops.py")


def test_biguint_one_const_vn(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "biguint_one_const_vn.py")


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


def test_loop_invariant_phi_aliasing(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "loop_invariant_phi_aliasing.py").client

    def run(x: int, y: int) -> int:
        result = client.send.call(
            au.AppClientMethodCallParams(method="run", args=[x, y], note=random.randbytes(8))
        ).abi_return
        assert isinstance(result, int)
        return result

    for x, y in [(1, 2), (3, 7), (5, 0), (0, 4)]:
        expected = x + 10 * (2 * y + x)
        actual = run(x, y)
        assert actual == expected, f"run({x}, {y}) gave {actual}, expected {expected}"


def test_redundant_phi_moving_vn(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "redundant_phi_moving_vn.py").client

    def run(n: int, y: int, *, cond: bool) -> int:
        result = client.send.call(
            au.AppClientMethodCallParams(method="run", args=[n, y, cond], note=random.randbytes(8))
        ).abi_return
        assert isinstance(result, int)
        return result

    # each iteration sets z = (z + y) + 1, starting from z = 0, so after n
    # iterations z = n * (y + 1) — independent of cond (both branches are equal).
    for n, y in [(0, 0), (1, 0), (3, 7), (5, 2), (10, 1)]:
        expected = n * (y + 1)
        for cond in (True, False):
            actual = run(n, y, cond=cond)
            assert (
                actual == expected
            ), f"run({n}, {y}, cond={cond}) gave {actual}, expected {expected}"


def test_partial_redundancy_elimination(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "partial_redundancy_elimination.py")


def test_replace3_const_fold(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "replace3_const_fold.py")


def test_scc_two_externals(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "scc_two_externals.py").client

    def call(a: int, b: int, n: int) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(
                method="test_alternating", args=[a, b, n], note=random.randbytes(8)
            )
        ).abi_return

    # alternating(a, b, n) returns (a + b) + n*(n-1)/2
    # (x and y swap each iteration so x+y is invariant; s accumulates 0..n-1)
    for a, b, n in [(0, 0, 0), (10, 20, 0), (10, 20, 1), (10, 20, 2), (10, 20, 3), (7, 13, 5)]:
        expected = a + b + n * (n - 1) // 2
        actual = call(a, b, n)
        assert actual == expected, f"alternating({a}, {b}, {n}) gave {actual}, expected {expected}"


def test_scc_vn_merged_externals(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "scc_vn_merged_externals.py").client

    def call(a: int, b: int, n: int) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(
                method="test_commutative_externals", args=[a, b, n], note=random.randbytes(8)
            )
        ).abi_return

    # alternating_with_commutative_inits(a, b, n) returns 2*(a|b) + n*(n-1)/2
    # (x and y both start as a|b — distinct Registers, same VN — so the SCC
    # collapses and the swap is a no-op; s accumulates 0..n-1)
    for a, b, n in [(0, 0, 0), (10, 20, 0), (10, 20, 1), (10, 20, 2), (10, 20, 3), (7, 13, 5)]:
        expected = 2 * (a | b) + n * (n - 1) // 2
        actual = call(a, b, n)
        assert actual == expected, (
            f"alternating_with_commutative_inits({a}, {b}, {n})"
            f" gave {actual}, expected {expected}"
        )


def test_wide_math_const_fold(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "gvn" / "wide_math_const_fold.py")


def test_one_const_simplification(deployer_o: Deployer) -> None:
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "one_const_simplification.py").client

    def call(method: str, args: list[object]) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(method=method, args=args, note=random.randbytes(8))
        ).abi_return

    assert call("mul_zero", [7]) == 0  # x * 0 -> 0
    assert call("mul_zero", [0]) == 0
    assert call("gt_zero", [0]) is False  # 0 > b -> 0
    assert call("gt_zero", [5]) is False
    assert call("lte_one", [0]) == 0  # (1 <= x) -> x; so 1 iff x != 0
    assert call("lte_one", [1]) == 1
    assert call("lte_one", [99]) == 1
    assert call("or_false", [True]) == 1  # (a or False) -> a
    assert call("or_false", [False]) == 0
    assert call("cond_gt_zero", [0]) == 0  # `0 > b` as a condition -> 0
    assert call("cond_gt_zero", [5]) == 0
    assert call("val_lte_one", [True]) is True  # (1 <= b) -> b
    assert call("val_lte_one", [False]) is False
    assert call("val_lt_zero", [True]) is True  # (0 < b) -> b
    assert call("val_lt_zero", [False]) is False

    # biguint one-const algebra: x b* 0 -> 0, and 0/1 identities preserve x
    for x in (0, 1, 12345, 2**200):
        assert call("bmul_zero", [x]) == 0
        assert call("badd_zero_left", [x]) == x
        assert call("badd_zero_right", [x]) == x
        assert call("bsub_zero", [x]) == x
        assert call("bdiv_one", [x]) == x


def test_declined_const_fold(deployer_o: Deployer) -> None:
    # GVN sees constant operands but declines to fold because the op would fail at
    # runtime, so the op is left in place and every method traps when called.
    client = deployer_o.create(TEST_CASES_DIR / "gvn" / "declined_const_fold.py").client

    for method in (
        "expw_zero_zero",
        "expw_overflow",
        "divw_div_zero",
        "divw_overflow",
        "divmodw_div_zero",
        "setbyte_value_oob",
        "bsqrt_too_long",
        "div_by_zero",
        "mod_by_zero",
        "biguint_mod_by_zero",
    ):
        with pytest.raises(au.LogicError):
            client.send.call(au.AppClientMethodCallParams(method=method, note=random.randbytes(8)))
