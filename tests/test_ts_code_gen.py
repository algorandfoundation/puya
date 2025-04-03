from pathlib import Path

from scripts.generate_ts_nodes import generate_file
from tests.utils.git import check_for_diff

VCS_ROOT = Path(__file__).parent.parent


def test_ts_code_gen() -> None:
    generate_file(out_path=VCS_ROOT / "tests" / "output" / "nodes.ts.txt")
    diff = check_for_diff(VCS_ROOT / "tests/output", VCS_ROOT)
    assert not diff, f"Uncommitted changes were found:\n{diff}"
