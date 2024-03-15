import os
import shutil
import subprocess
from pathlib import Path

from tests import EXAMPLES_DIR, TEST_CASES_DIR, VCS_ROOT

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}


def run_puyapy(
    args: list[str | Path], *, check: bool = True, text: bool = True
) -> subprocess.CompletedProcess[str]:
    puyapy = shutil.which("puyapy")
    assert puyapy is not None
    result = subprocess.run(
        [  # noqa: S603
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
        env=ENV_WITH_NO_COLOR,
    )
    if check:
        assert result.returncode == 0, result.stdout
    return result


def test_run_no_args() -> None:
    result = run_puyapy([], check=False)
    assert result.returncode == 2


def test_run_version() -> None:
    result = run_puyapy(["--version"], check=False)
    assert result.returncode == 0
    assert result.stdout.startswith("puyapy")


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
