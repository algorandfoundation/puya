import algokit_utils as au
import pytest

from tests import AWST_DIR, TEST_CASES_DIR
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


_EXTRACT_PATH = TEST_CASES_DIR / "regression_tests" / "extract_fold_oob.py"


def test_extract_length_oob(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match="extraction end 5 is beyond length: 1"):
        deployer_o.create_bare((_EXTRACT_PATH, "ExtractLengthOOB"))


def test_extract_start_oob(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match="extraction start 5 is beyond length: 1"):
        deployer_o.create_bare((_EXTRACT_PATH, "ExtractStartOOB"))


def test_substring_end_oob(deployer_o: Deployer) -> None:
    with pytest.raises(au.LogicError, match="substring3: end index beyond end of source"):
        deployer_o.create_bare((_EXTRACT_PATH, "SubstringEndOOB"))


def test_logical_fold_non_bool(deployer_o: Deployer) -> None:
    # && and || with non-boolean constant operands should return 0 or 1 on the AVM.
    # Without the fix, the optimizer folds 5 && 3 to 3 instead of 1.
    deployer_o.create_bare(AWST_DIR / "logical_fold_non_bool")


def test_logical_fold_or_identity(deployer_o: Deployer) -> None:
    # 0 || x and x || 0 should return 0 or 1 on the AVM when x is a non-bool uint64.
    # Without the fix, the optimizer folds these to x unconditionally.
    deployer_o.create_bare(AWST_DIR / "logical_fold_or_identity", args=[5])


_OP_SELECTION_PATH = TEST_CASES_DIR / "regression_tests" / "op_variant_selection.py"


def test_replace_op_selection(deployer_o: Deployer) -> None:
    # index > 255 must select replace3 (uint64 stack) over replace2 (uint8 immediate)
    deployer_o.create_bare((_OP_SELECTION_PATH, "ReplaceOpSelection"))


def test_extract_op_selection(deployer_o: Deployer) -> None:
    # index/length > 255 must select extract3 (uint64 stack args) over extract (uint8 immediates)
    deployer_o.create_bare((_OP_SELECTION_PATH, "ExtractOpSelection"))


def test_substring_op_selection(deployer_o: Deployer) -> None:
    # start/end > 255 must select substring3 (uint64 stack args) over substring (uint8 immediates)
    deployer_o.create_bare((_OP_SELECTION_PATH, "SubstringOpSelection"))


def test_gaid_op_selection(deployer_o: Deployer) -> None:
    # T > 255 must select gaids (uint64 stack arg) over gaid (uint8 immediate).
    # Compile selects the stack variant; at runtime 256 exceeds the group index so it logic-errors.
    with pytest.raises(au.LogicError, match=r"gaids lookup TxnGroup\[256\] but it only has 1"):
        deployer_o.create_bare((_OP_SELECTION_PATH, "GaidOpSelection"))


def test_gload_t_op_selection(deployer_o: Deployer) -> None:
    # T > 255, I <= 255: optimizer downgrades gloadss -> gloads at O1+ (I immediate,
    # T on stack) or leaves as gloadss at O0. Runtime fails since T is unreachable.
    with pytest.raises(au.LogicError, match=r"gloadss? lookup TxnGroup\[256\] but it only has 1"):
        deployer_o.create_bare((_OP_SELECTION_PATH, "GloadTOpSelection"))


def test_gload_i_op_selection(deployer_o: Deployer) -> None:
    # T <= 255, I > 255: no op variant has T immediate with I on stack, so gloadss
    # must be preserved at all optimization levels. Runtime fails on the scratch
    # slot lookup.
    with pytest.raises(au.LogicError, match=r"gloadss scratch index >= 256"):
        deployer_o.create_bare((_OP_SELECTION_PATH, "GloadIOpSelection"))


def test_txn_array_op_selection(deployer_o: Deployer) -> None:
    # I > 255 must select txnas (uint64 stack arg) over txna (uint8 immediate).
    # At runtime 256 exceeds ApplicationArgs length so it logic-errors.
    with pytest.raises(au.LogicError, match=r"invalid ApplicationArgs index 256"):
        deployer_o.create_bare((_OP_SELECTION_PATH, "TxnArrayOpSelection"))


def test_gtxn_op_selection(deployer_o: Deployer) -> None:
    # T > 255 must select gtxns (uint64 stack arg) over gtxn (uint8 immediate).
    # At runtime 256 exceeds the group index so it logic-errors.
    with pytest.raises(au.LogicError, match=r"txn index 256, len\(group\) is 1"):
        deployer_o.create_bare((_OP_SELECTION_PATH, "GTxnOpSelection"))


def test_gtxn_array_group_op_selection(deployer_o: Deployer) -> None:
    # T > 255, I <= 255 must select gtxnsa (I immediate, T on stack) at O1+, or leave as
    # gtxnsas at O0. Either way the group index 256 is unreachable at runtime.
    with pytest.raises(au.LogicError, match=r"txn index 256, len\(group\) is 1"):
        deployer_o.create_bare((_OP_SELECTION_PATH, "GTxnArrayGroupOpSelection"))


def test_gtxn_array_index_op_selection(deployer_o: Deployer) -> None:
    # T <= 255, I > 255 must select gtxnas (T immediate, I on stack) at O1+, or leave as
    # gtxnsas at O0. Either way ApplicationArgs[256] is beyond the array at runtime.
    with pytest.raises(au.LogicError, match=r"invalid ApplicationArgs index 256"):
        deployer_o.create_bare((_OP_SELECTION_PATH, "GTxnArrayIndexOpSelection"))
