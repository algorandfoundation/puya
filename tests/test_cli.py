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
        [
            puyapy,
            # we don't want to overwrite outputs, just check the CLI works,
            "--no-output-teal",
            "--no-output-bytecode",
            "--no-output-source-map",
            "--no-output-client",
            "--no-output-arc32",
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


def run_puyapy_clientgen(
    path: Path,
    *flags: str,
) -> subprocess.CompletedProcess[str]:
    puyapy_clientgen = shutil.which("puyapy-clientgen")
    assert puyapy_clientgen is not None
    result = subprocess.run(
        [
            puyapy_clientgen,
            str(path),
            *flags,
        ],
        text=True,
        # capture stdout
        stdout=subprocess.PIPE,
        # redirect stderr to stdout, so they're interleaved in the correct ordering
        stderr=subprocess.STDOUT,
        cwd=VCS_ROOT,
        check=False,
        env=ENV_WITH_NO_COLOR,
    )
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


def test_run_single_file_with_other_references(tmpdir: Path) -> None:
    run_puyapy(
        [
            TEST_CASES_DIR / "compile" / "factory.py",
            "--output-bytecode",
            "--out-dir",
            str(tmpdir),
        ]
    )


def test_run_multiple_files() -> None:
    run_puyapy(
        [
            EXAMPLES_DIR / Path("calculator") / "contract.py",
            TEST_CASES_DIR / Path("simple") / "contract.py",
        ]
    )


def test_run_directory() -> None:
    run_puyapy([TEST_CASES_DIR / "simple"])


def test_puyapy_clientgen_arc32(tmpdir: Path) -> None:
    # ARC-32 output differs slightly from ARC-56, so we are just checking it doesn't error
    # and ignore the generated artifact
    path = TEST_CASES_DIR / "arc_56" / "out" / "Contract.arc32.json"
    run_puyapy_clientgen(path, "--out-dir", str(tmpdir))


def test_puyapy_clientgen_arc56() -> None:
    path = TEST_CASES_DIR / "arc_56" / "out" / "Contract.arc56.json"
    run_puyapy_clientgen(path)
