import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests import VCS_ROOT

pytestmark = pytest.mark.pyinstaller_binary_tests

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}
DUMMY_HELLO_WORLD_AWST = Path(
    Path(__file__).parent / "artifacts" / "hello_world.awst.json"
).read_text()


def run_puya(
    args: list[str | Path], *, check: bool = True, text: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run the puya CLI module directly using the python -m syntax."""
    python = shutil.which("python")
    assert python is not None
    result = subprocess.run(
        [
            "puya",
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
    result = run_puya([], check=False)
    assert result.returncode == 2
    assert "error: the following arguments are required: --options, --awst" in result.stdout


def test_run_version() -> None:
    result = run_puya(["--version"])
    assert result.returncode == 0
    assert result.stdout.startswith("puya")


def test_run_with_invalid_options() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        options_path = Path(tmpdir) / "options.json"
        awst_path = Path(tmpdir) / "awst.json"

        # Write invalid JSON to options file
        options_path.write_text("{invalid json")
        # Write empty JSON to AWST file
        awst_path.write_text("{}")

        result = run_puya(["--options", options_path, "--awst", awst_path], check=False)
        assert result.returncode != 0
        assert "error" in result.stdout.lower()


def test_run_with_valid_options() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        options_path = Path(tmpdir) / "options.json"
        awst_path = Path(tmpdir) / "awst.json"
        dummy_output_path = Path(tmpdir)

        # Write minimal valid options
        target_id = "examples.hello_world.contract.HelloWorldContract"
        options = {
            "output_teal": True,
            "output_arc56": True,
            "compilation_set": {target_id: str(dummy_output_path)},
        }
        options_path.write_text(json.dumps(options))
        # Write minimal valid AWST (empty array)
        awst_path.write_text(DUMMY_HELLO_WORLD_AWST)

        result = run_puya(["--options", options_path, "--awst", awst_path])
        # Should complete without error

        assert result.returncode == 0
