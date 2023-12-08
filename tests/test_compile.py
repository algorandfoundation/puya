import shutil
import subprocess
from pathlib import Path

VCS_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = VCS_ROOT / "examples"


def run_algopy(
    args: list[str | Path], *, check: bool = True, text: bool = True
) -> subprocess.CompletedProcess[str]:
    algopy = shutil.which("puya")
    assert algopy is not None
    result = subprocess.run(
        [
            algopy,
            "--no-output-teal",  # we don't want to overwrite outputs, just check the CLI works
            *map(str, args),
        ],
        text=text,
        # capture stdout
        stdout=subprocess.PIPE,
        # redirect stderr to stdout, so they're interleaved in the correct ordering
        stderr=subprocess.STDOUT,
        cwd=EXAMPLES_DIR,
        check=False,
    )
    if check:
        assert result.returncode == 0, result.stdout
    return result


def test_run_no_args() -> None:
    result = run_algopy([], check=False)
    assert result.returncode == 2


def test_run_not_python() -> None:
    result = run_algopy(["../pyproject.toml"], check=False)
    assert result.returncode == 1
    assert "error: invalid syntax" in result.stdout


def test_run_single_file() -> None:
    run_algopy([Path("simple") / "contract.py"])


def test_run_multiple_files() -> None:
    run_algopy(
        [
            Path("calculator") / "contract.py",
            Path("simple") / "contract.py",
        ]
    )


def test_run_directory() -> None:
    run_algopy(["simple"])
