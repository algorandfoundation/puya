from pathlib import Path

from tests import FROM_AWST_DIR
from tests.from_awst.util import compile_contract


def test_compile() -> None:
    test_dir = Path(__file__).parent
    out_dir = test_dir / "out"

    compile_contract(
        awst_path=FROM_AWST_DIR / "native_array" / "module.awst.json",
        compilation_set={"tests/approvals/native-arrays.algo.ts::NativeArraysAlgo": out_dir},
    )
