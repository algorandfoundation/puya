import shutil
import subprocess
from pathlib import Path


def check_for_diff(path: Path, cwd: Path) -> str | None:
    git = shutil.which("git")
    assert git, "could not find git"
    assert path.is_dir()
    result = subprocess.run(
        [git, "diff", str(path)],
        check=True,
        capture_output=True,
        cwd=cwd,
    )
    return result.stdout.decode("utf8")
