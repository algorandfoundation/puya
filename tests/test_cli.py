import shutil
import subprocess
from pathlib import Path

from tests.conftest import EXAMPLES_DIR, TEST_CASES_DIR, VCS_ROOT


def run_puyapy(
    args: list[str | Path], *, check: bool = True, text: bool = True
) -> subprocess.CompletedProcess[str]:
    puyapy = shutil.which("puyapy")
    assert puyapy is not None
    result = subprocess.run(
        [
            puyapy,
            "--no-output-teal",  # we don't want to overwrite outputs, just check the CLI works
            *map(str, args),
        ],
        text=text,
        # capture stdout
        stdout=subprocess.PIPE,
        # redirect stderr to stdout, so they're interleaved in the correct ordering
        stderr=subprocess.STDOUT,
        cwd=VCS_ROOT,
        check=False,
    )
    if check:
        assert result.returncode == 0, result.stdout
    return result


def test_run_no_args() -> None:
    result = run_puyapy([], check=False)
    assert result.returncode == 2


def test_run_not_python() -> None:
    result = run_puyapy(["pyproject.toml"], check=False)
    assert result.returncode == 1
    assert "error: invalid syntax" in result.stdout


def test_run_single_file() -> None:
    run_puyapy([TEST_CASES_DIR / Path("simple") / "contract.py"])


def test_run_multiple_files() -> None:
    run_puyapy(
        [
            EXAMPLES_DIR / Path("calculator") / "contract.py",
            TEST_CASES_DIR / Path("simple") / "contract.py",
        ]
    )


def test_run_directory() -> None:
    run_puyapy([TEST_CASES_DIR / "simple"])
