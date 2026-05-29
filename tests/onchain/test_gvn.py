import random

import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

GVN_DIR = TEST_CASES_DIR / "gvn"


def test_const_folding(deployer_o: Deployer) -> None:
    # bare contract: every fold is asserted in the approval program, so deploying and
    # running it is the check (setbyte/mod, getbyte, replace3, wide-math, btoi(itob)).
    deployer_o.create_bare(GVN_DIR / "const_folding.py")


def test_algebraic_identities(deployer_o: Deployer) -> None:
    # bare contract: self-operand folds, biguint one-const, comparison swaps and
    # negation — all asserted in-program.
    deployer_o.create_bare(GVN_DIR / "algebraic_identities.py")


def test_phi_congruence(deployer_o: Deployer) -> None:
    client = deployer_o.create(GVN_DIR / "phi_congruence.py").client

    def call(method: str, args: list[object]) -> object:
        return client.send.call(
            au.AppClientMethodCallParams(method=method, args=args, note=random.randbytes(8))
        ).abi_return

    # phi / SCC congruence
    assert call("test_cross_assignment", [42]) == 84
    assert call("test_cross_assignment", [0]) == 0
    assert call("test_triple_cycle", [10]) == 30
    assert call("test_redundant_phi", [0, 5]) == 0 | 5
    assert call("test_redundant_phi", [7, 5]) == 7 | 5
    assert call("test_replacement_chain", [0]) == 0
    assert call("test_replacement_chain", [42]) == 84
    with pytest.raises(au.LogicError, match="dynamic cost budget exceeded"):
        call("test_replacement_chain", [1])

    # SCC external classification:
    #   alternating(a, b, n)        = (a + b) + n*(n-1)/2   (x, y swap; x+y invariant)
    #   commutative variant         = 2*(a|b) + n*(n-1)/2   (a|b == b|a, SCC collapses)
    for a, b, n in [(0, 0, 0), (10, 20, 0), (10, 20, 1), (10, 20, 2), (10, 20, 3), (7, 13, 5)]:
        triangular = n * (n - 1) // 2
        assert call("test_alternating", [a, b, n]) == a + b + triangular
        assert call("test_commutative_externals", [a, b, n]) == 2 * (a | b) + triangular

    # nested-loop phi SCC with a single external VN (n) collapses to n
    for n, p, q in [(0, 0, 0), (5, 3, 4), (42, 2, 2)]:
        assert call("test_nested_scc_collapse", [n, p, q]) == n

    # optimistic-iteration mechanics
    # test_moving_vn: each iteration sets z = (z + y) + 1, so z = n*(y+1) (cond-independent)
    for n, y in [(0, 0), (1, 0), (3, 7), (5, 2), (10, 1)]:
        for cond in (True, False):
            actual = call("test_moving_vn", [n, y, cond])
            assert actual == n * (y + 1), f"test_moving_vn({n}, {y}, cond={cond}) -> {actual}"
    # test_loop_invariant: z = x + 10*(2y + x)
    for x, y in [(1, 2), (3, 7), (5, 0), (0, 4)]:
        actual = call("test_loop_invariant", [x, y])
        assert actual == x + 10 * (2 * y + x), f"test_loop_invariant({x}, {y}) -> {actual}"
    # test_deep_nesting: forces the pessimistic fallback; for runnable n every index is 0
    # so the accumulator is 0 — this confirms the fallback path executes without trapping.
    assert call("test_deep_nesting", [0]) == 0
    assert call("test_deep_nesting", [1]) == 0

    # commutative-equality assert elimination: result == a + b for both branches
    for cond in (True, False):
        assert call("test_commutative_add_assert", [3, 5, cond]) == 8


def test_one_const_simplification(deployer_o: Deployer) -> None:
    client = deployer_o.create(
        (GVN_DIR / "one_const_simplification.py", "OneConstSimplificationContract")
    ).client

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
    client = deployer_o.create(
        (GVN_DIR / "one_const_simplification.py", "DeclinedConstFoldContract")
    ).client

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
