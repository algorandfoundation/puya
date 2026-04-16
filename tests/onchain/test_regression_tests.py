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


def test_xor_identity_fold_biguint(deployer_o: Deployer) -> None:
    deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "xor_identity_fold_biguint.py")


def test_gebit_bytes_fold_oob(deployer_o: Deployer) -> None:
    # solves compiler crash when trying to fold OOB getbit acces into Bytes constant.
    with pytest.raises(au.LogicError, match="had error 'getbit index beyond byteslice'"):
        deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "getbit_fold_oob_bytes.py")


def test_getbit_uint64_fold_oob(deployer_o: Deployer) -> None:
    # OOB getbit access in uint64 should panic on the AVM.
    # Without the fix, the optimizer folds this to UInt64(0) and the panic is lost.
    with pytest.raises(au.LogicError, match="had error 'getbit index > 63 with Uint'"):
        deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "getbit_fold_oob_uint64.py")
