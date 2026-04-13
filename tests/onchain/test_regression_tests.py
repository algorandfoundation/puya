import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_regression_194(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "issue_194.py")


def test_div_identity_fold_uint64(deployer_o: Deployer) -> None:
    # self_div(UInt64(0)) does `0 // 0` which should panic on the AVM.
    # Without the fix, the optimizer folds `x // x` to `1` and the panic is lost.
    with pytest.raises(au.LogicError, match="had error '/ 0'"):
        deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "div_identity_fold_uint64.py")


def test_div_identity_fold_biguint(deployer_o: Deployer) -> None:
    # self_div(BigUInt(0)) does `0 b/ 0` which should panic on the AVM.
    # Without the fix, the optimizer folds `x // x` to `1` and the panic is lost.
    with pytest.raises(au.LogicError, match="had error 'division by zero'"):
        deployer_o.create_bare(
            TEST_CASES_DIR / "regression_tests" / "div_identity_fold_biguint.py"
        )
