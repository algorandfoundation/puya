#!/usr/bin/env python3
import json
import operator
import os
import shutil
import subprocess
import sys
import tempfile
import typing
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import attrs
import cyclopts

from puya.awst.serialize import awst_from_json
from puya.log import configure_stdio
from tests.utils import (
    OPT_SUFFIXES,
    PuyaTestCase,
    get_puya_options_for_optimization,
    get_test_cases,
)
from tests.utils.compile import (
    UNSTABLE_LOG_PREFIXES,
    get_compilation_set,
    load_test_case_json,
    normalize_arc56,
    normalize_log,
)

# iterate optimization levels first and with O1 first and then cases, this is a workaround
# to prevent race conditions that occur when the mypy parsing stage of O0, O2 tries to
# read the client_<contract>.py output from the 01 level before it is finished writing to
# disk
DEFAULT_OPTIMIZATION = (1, 0, 2)

app = cyclopts.App(help_on_error=True)


@app.default
def main(
    limit_to: typing.Annotated[
        Sequence[cyclopts.types.ExistingPath],
        cyclopts.Parameter(name="LIMIT_TO", negative=()),
    ] = (),
    /,
    *,
    optimization_level: typing.Annotated[
        Sequence[typing.Literal[0, 1, 2]], cyclopts.Parameter(alias="-O", negative=())
    ] = (),
) -> None:
    """
    Compiles test cases using puyapy or puya as an end-to-end test

    Parameters:
        limit_to: Paths of test cases to filter to e.g. (test_cases/arc4_types)
        optimization_level: Which optimization levels to output TEAL / AVM bytecode at
    """
    configure_stdio()
    if limit_to:
        to_compile = [PuyaTestCase(Path(x).resolve()) for x in limit_to]
    else:
        to_compile = get_test_cases()

    failures = list[tuple[str, str]]()
    # use selected opt levels, but retain original order
    opt_levels = [
        o for o in DEFAULT_OPTIMIZATION if o in (optimization_level or DEFAULT_OPTIMIZATION)
    ]
    with ProcessPoolExecutor() as executor:
        args = [(case, level) for level in opt_levels for case in to_compile]
        for compilation_result, level in executor.map(_compile_for_level, args):
            rel_path = compilation_result.rel_path
            case_name = f"{rel_path} -O{level}"
            if compilation_result.ok:
                print(f"✅  {case_name}")
            else:
                print(f"💥 {case_name}", file=sys.stderr)
                failures.append((case_name, compilation_result.stdout))

    if failures:
        print("Compilation failures:")
        for name, stdout in sorted(failures, key=operator.itemgetter(0)):
            print(f" ~~~ {name} ~~~ ")
            print(
                "\n".join(
                    ln
                    for ln in stdout.splitlines()
                    if (ln.startswith("debug: Traceback ") or not ln.startswith("debug: "))
                )
            )
    sys.exit(len(failures))


_LOGS_TO_FILTER = (
    "info: using puyapy version",
    *(f"{level.name}: {msg}" for level, msgs in UNSTABLE_LOG_PREFIXES.items() for msg in msgs),
)


def _stabilise_logs(stdout: str) -> str:
    return "\n".join(
        normalize_log(line) for line in stdout.splitlines() if not line.startswith(_LOGS_TO_FILTER)
    )


def _clean_out_dir(out_dir: Path) -> None:
    if out_dir.exists():
        for prev_out_file in out_dir.iterdir():
            if prev_out_file.is_dir():
                shutil.rmtree(prev_out_file)
            else:
                prev_out_file.unlink()


@attrs.define
class CompilationResult:
    rel_path: str
    ok: bool
    stdout: str


def _compile_for_level(arg: tuple[PuyaTestCase, int]) -> tuple[CompilationResult, int]:
    test_case, optimization_level = arg
    if test_case.is_awst:
        compile_for_level = _compile_for_level_awst
    else:
        compile_for_level = _compile_for_level_python

    return compile_for_level(test_case, optimization_level), optimization_level


def _compile_for_level_python(
    test_case: PuyaTestCase, optimization_level: int
) -> CompilationResult:
    flags = [
        _option_to_flag(option, value)
        for option, value in get_puya_options_for_optimization(optimization_level).items()
    ]
    out_suffix = OPT_SUFFIXES[optimization_level]
    out_dir = (test_case.path / f"out{out_suffix}").resolve()
    cmd = [
        "uv",
        "run",
        "puyapy",
        *flags,
        f"--out-dir={out_dir}",
        "--log-level=debug",
        *_load_template_vars(test_case.path / "template.vars"),
        test_case.name,
    ]
    return _run_compile(test_case, cmd, out_dir=out_dir, out_suffix=out_suffix)


def _compile_for_level_awst(test_case: PuyaTestCase, optimization_level: int) -> CompilationResult:
    out_suffix = OPT_SUFFIXES[optimization_level]
    out_dir = (test_case.test_case / f"out{out_suffix}").resolve()

    awst_json_str = load_test_case_json(test_case.path)
    awst = awst_from_json(awst_json_str)
    options = dict(get_puya_options_for_optimization(optimization_level))
    options["compilation_set"] = {k: str(v) for k, v in get_compilation_set(awst, out_dir).items()}

    with tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        awst_file = tmp_dir / "module.awst.json"
        awst_file.write_text(awst_json_str, encoding="utf-8")
        options_file = tmp_dir / "options.json"
        options_file.write_text(json.dumps(options), encoding="utf-8")

        cmd = [
            "uv",
            "run",
            "puya",
            f"--awst={awst_file}",
            f"--options={options_file}",
            "--log-level=debug",
        ]
        return _run_compile(test_case, cmd, out_dir=out_dir, out_suffix=out_suffix)


ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
}


def _run_compile(
    test_case: PuyaTestCase, cmd: list[str], *, out_dir: Path, out_suffix: str
) -> CompilationResult:
    _clean_out_dir(out_dir)
    out_dir.mkdir(exist_ok=True)

    result = subprocess.run(
        cmd,
        cwd=test_case.root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=ENV_WITH_NO_COLOR,
        encoding="utf-8",
    )

    normalize_arc56(out_dir)

    log_path = test_case.test_case / f"puya{out_suffix}.log"
    logs = _stabilise_logs(result.stdout)
    log_path.write_text(logs, encoding="utf8")

    ok = result.returncode == 0
    return CompilationResult(
        rel_path=test_case.name,
        ok=ok,
        stdout=result.stdout if not ok else "",  # don't thunk stdout if no errors
    )


def _load_template_vars(path: Path) -> Iterable[str]:
    if path.exists():
        for line in path.read_text("utf8").splitlines():
            if line.startswith("prefix="):
                prefix = line.removeprefix("prefix=")
                yield f"--template-vars-prefix={prefix}"
            else:
                yield f"-T={line}"


def _option_to_flag(option: str, value: object) -> str:
    option = option.replace("_", "-")
    if option.startswith("output"):
        if not value:
            option = f"no-{option}"
        return f"--{option}"
    return f"--{option}={value}"


if __name__ == "__main__":
    app()
