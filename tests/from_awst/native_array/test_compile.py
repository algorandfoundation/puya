import shutil
import subprocess
from pathlib import Path

from tests import VCS_ROOT
from tests.utils.git import check_for_diff


def test_compile() -> None:
    this_dir = Path(__file__).parent
    out_dir = this_dir / "out"
    shutil.rmtree(out_dir, ignore_errors=True)
    subprocess.run(
        "puya --awst=module.awst.json.zip --options=options.json --log-level=debug".split(),
        check=True,
        cwd=this_dir,
    )
    diff = check_for_diff(out_dir, VCS_ROOT)
    assert not diff, f"Uncommitted changes were found:\n{diff}"
