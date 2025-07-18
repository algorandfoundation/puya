from pathlib import Path

from tests import FROM_AWST_DIR
from tests.from_awst.util import compile_contract


def test_compile() -> None:
    test_dir = Path(__file__).parent
    out_dir = test_dir / "out"

    compile_contract(
        awst_path=FROM_AWST_DIR / "ops_should_be_mutated" / "module.awst.json",
        compilation_set={"tests/approvals/mutable-object.algo.ts::MutableObjectDemo": out_dir},
    )
