import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory

import attrs
import pytest
from cattrs.preconf.json import make_converter

from puya.main import PuyaOptionsWithCompilationSet
from tests import EXAMPLES_DIR, TEST_CASES_DIR, VCS_ROOT

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
}


def run_puyapy(args: list[str | Path], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    puyapy = shutil.which("puyapy")
    assert puyapy is not None, "puyapy not found"
    return _run(
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
        check=check,
    )


def run_puya(args: list[str | Path]) -> subprocess.CompletedProcess[str]:
    puya = shutil.which("puya")
    assert puya is not None, "puya not found"
    return _run(
        [
            puya,
            *map(str, args),
        ]
    )


def run_puyapy_clientgen(
    path: Path,
    *flags: str,
) -> subprocess.CompletedProcess[str]:
    puyapy_clientgen = shutil.which("puyapy-clientgen")
    assert puyapy_clientgen is not None, "puyapy-clientgen not found"
    return _run(
        [
            puyapy_clientgen,
            str(path),
            *flags,
        ]
    )


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        text=True,
        # capture stdout
        stdout=subprocess.PIPE,
        # redirect stderr to stdout, so they're interleaved in the correct ordering
        stderr=subprocess.STDOUT,
        cwd=VCS_ROOT,
        check=False,
        env=ENV_WITH_NO_COLOR,
    )
    if check and result.returncode != 0:
        pytest.fail(f"{args[0]} failed: {result.stdout}")
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


@pytest.fixture
def hello_world_awst_json() -> Iterable[Path]:
    path = EXAMPLES_DIR / "hello_world_arc4"
    with TemporaryDirectory() as tmp_dir:
        run_puyapy(["--output-awst-json", "--out-dir", tmp_dir, path])
        awst_json = Path(tmp_dir) / "module.awst.json"
        yield awst_json


_OUTPUT_OPTIONS = [
    field.name
    for field in attrs.fields(PuyaOptionsWithCompilationSet)
    if field.name.startswith("output_") and field.type is bool
]


@pytest.mark.parametrize("output_option", _OUTPUT_OPTIONS)
def test_puya_output(hello_world_awst_json: Path, output_option: str) -> None:
    with TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        assert hello_world_awst_json.exists(), "expected awst json to exist"
        options_json = tmp_dir / "options.json"
        out_dir = tmp_dir / "nested" / "out"
        options = PuyaOptionsWithCompilationSet(
            **{output_option: True},  # type: ignore[arg-type]
            optimization_level=0,
            compilation_set={"examples.hello_world_arc4.contract.HelloWorldContract": out_dir},
        )
        converter = make_converter()
        options_json.write_text(converter.dumps(options), encoding="utf8")
        assert not out_dir.exists(), "precondition, out dir does not yet exist"
        run_puya(
            ["--awst", hello_world_awst_json, "--options", options_json, "--log-level", "debug"]
        )
        assert out_dir.exists(), "out dir should exist"
