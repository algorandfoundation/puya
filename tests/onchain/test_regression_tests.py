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


def test_getbit_bytes_fold_oob(deployer_o: Deployer) -> None:
    # solves compiler crash when trying to fold OOB getbit acces into Bytes constant.
    with pytest.raises(au.LogicError, match="had error 'getbit index beyond byteslice'"):
        deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "getbit_fold_oob_bytes.py")


def test_getbit_uint64_fold_oob(deployer_o: Deployer) -> None:
    # OOB getbit access in uint64 should panic on the AVM.
    # Without the fix, the optimizer folds this to UInt64(0) and the panic is lost.
    with pytest.raises(au.LogicError, match="had error 'getbit index > 63 with Uint'"):
        deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "getbit_fold_oob_uint64.py")


def test_setbit_uint64_fold_oob(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match="setbit index > 63 with Uint"):
        deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "setbit_fold_oob_uint64.py")


def test_shl_fold_oob(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match=r"shl arg too big, \(64\)"):
        deployer_o.create_bare(
            (TEST_CASES_DIR / "regression_tests" / "shift_fold_oob.py", "ShlFoldOOB")
        )


def test_shr_fold_oob(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match=r"shr arg too big, \(64\)"):
        deployer_o.create_bare(
            (TEST_CASES_DIR / "regression_tests" / "shift_fold_oob.py", "ShrFoldOOB")
        )


def test_replace_fold_oob(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match="replacement end 3 beyond original length: 0"):
        deployer_o.create_bare(TEST_CASES_DIR / "regression_tests" / "replace_fold_oob.py")


def test_uint64_add_overflow_fold(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match=r"\+ overflowed"):
        deployer_o.create_bare(
            (TEST_CASES_DIR / "regression_tests" / "uint64_overflow_fold.py", "UInt64AddOverflow")
        )


def test_uint64_mul_overflow_fold(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match=r"\* overflowed"):
        deployer_o.create_bare(
            (TEST_CASES_DIR / "regression_tests" / "uint64_overflow_fold.py", "UInt64MulOverflow")
        )


def test_uint64_exp_overflow_fold(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match=r"2\^64 overflow"):
        deployer_o.create_bare(
            (TEST_CASES_DIR / "regression_tests" / "uint64_overflow_fold.py", "UInt64ExpOverflow")
        )


def test_uint64_triple_add_overflow_fold(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match=r"\+ overflowed"):
        deployer_o.create_bare(
            (
                TEST_CASES_DIR / "regression_tests" / "uint64_triple_overflow_fold.py",
                "UInt64TripleAddOverflow",
            )
        )


def test_uint64_triple_mul_overflow_fold(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match=r"\* overflowed"):
        deployer_o.create_bare(
            (
                TEST_CASES_DIR / "regression_tests" / "uint64_triple_overflow_fold.py",
                "UInt64TripleMulOverflow",
            )
        )
