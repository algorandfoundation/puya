import os
import shutil
import subprocess
import typing
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path

import attrs
import pytest
from _pytest.mark import ParameterSet
from puya import log
from puya.options import PuyaOptions

from tests import VCS_ROOT
from tests.utils import (
    APPROVAL_EXTENSIONS,
    PuyaExample,
    compile_src_from_options,
    get_all_examples,
    get_relative_path,
)

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}
SUFFIX_O0 = "_unoptimized"
SUFFIX_O1 = ""
SUFFIX_O2 = "_O2"


def _should_output(path: Path, puya_options: PuyaOptions) -> bool:
    for pattern, include_in_output in {
        "*.teal": puya_options.output_teal,
        "*.arc32.json": puya_options.output_arc32,
        "*.awst": puya_options.output_awst,
        "*.ssa.ir": puya_options.output_ssa_ir,
        "*.ssa.opt_pass_*.ir": puya_options.output_optimization_ir,
        "*.destructured.ir": puya_options.output_destructured_ir,
        "*.mir": puya_options.output_memory_ir,
    }.items():
        if include_in_output and fnmatch(path.name, pattern):
            return True
    return False


def compile_test_case(
    test_case: PuyaExample, suffix: str, log_path: Path | None = None, **options: typing.Any
) -> None:
    path = test_case.path.resolve()
    if path.is_dir():
        dst_out_dir = path / ("out" + suffix)
    else:
        dst_out_dir = path.parent / f"{path.stem}_out{suffix}"

    puya_options = PuyaOptions(
        paths=(test_case.path,),
        out_dir=dst_out_dir,
        log_level=log.LogLevel.debug,
        template_vars_path=test_case.template_vars_path,
        **options,
    )
    compile_result = compile_src_from_options(puya_options)

    if log_path:
        root_dir = compile_result.root_dir
        log_options = attrs.evolve(puya_options, paths=(Path(test_case.name),))
        logs = [_log_to_str(log_, root_dir) for log_ in compile_result.logs]
        logs.insert(0, f"debug: {log_options}")
        log_path.write_text(
            "\n".join(map(_normalize_log, logs)),
            encoding="utf8",
        )


def _normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


_NORMALIZED_VCS = _normalize_path(VCS_ROOT)


def _normalize_log(log: str) -> str:
    return log.replace("\\", "/").replace(_NORMALIZED_VCS, "<git root>")


def _log_to_str(log: log.Log, root_dir: Path) -> str:
    if log.location:
        relative_path = get_relative_path(log.location, root_dir)
        col = f":{log.location.column + 1}" if log.location.column else ""
        location = f"{relative_path!s}:{log.location.line}{col} "
    else:
        location = ""
    return f"{location}{log.level}: {log.message}"


def compile_no_optimization(test_case: PuyaExample) -> None:
    compile_test_case(
        test_case,
        SUFFIX_O0,
        optimization_level=0,
        output_teal=True,
        output_bytecode=True,
        output_awst=False,
        output_destructured_ir=True,
        output_arc32=False,
    )


def compile_with_level1_optimizations(test_case: PuyaExample) -> None:
    compile_test_case(
        test_case,
        SUFFIX_O1,
        log_path=test_case.path / "puya.log",
        optimization_level=1,
        output_teal=True,
        output_bytecode=True,
        output_arc32=True,
        output_awst=True,
        output_ssa_ir=True,
        output_optimization_ir=True,
        output_destructured_ir=True,
        output_memory_ir=True,
        output_client=True,
    )


def compile_with_level2_optimizations(test_case: PuyaExample) -> None:
    compile_test_case(
        test_case,
        SUFFIX_O2,
        optimization_level=2,
        debug_level=0,
        output_teal=True,
        output_bytecode=True,
        output_arc32=False,
        output_destructured_ir=True,
        output_optimization_ir=False,
    )


def get_test_cases() -> Iterable[ParameterSet]:
    for example in get_all_examples():
        if example.name == "stress_tests":
            marks = [pytest.mark.slow]
        else:
            marks = []
        yield ParameterSet.param(example, marks=marks, id=example.id)


def remove_output(path: Path) -> None:
    (path / "puya.log").unlink(missing_ok=True)
    for out_suffix in (SUFFIX_O0, SUFFIX_O1, SUFFIX_O2):
        out_dir = path / f"out{out_suffix}"
        if out_dir.exists():
            for file in out_dir.iterdir():
                if file.suffix in APPROVAL_EXTENSIONS:
                    file.unlink()


def check_for_diff(path: Path) -> str | None:
    git = shutil.which("git")
    assert git is not None, "could not find git"
    if path.is_dir():
        paths = [path]
    else:
        paths = list(path.parent.glob(f"{path.stem}_out*"))
        paths.append(path.with_suffix(".puya.log"))
    stdout = ""
    for path in paths:
        result = subprocess.run(
            [git, "diff", str(path)],  # noqa: S603
            check=True,
            capture_output=True,
            cwd=VCS_ROOT,
        )
        stdout += result.stdout.decode("utf8")
    return stdout or None


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    metafunc.parametrize("case", get_test_cases())


def test_cases(case: PuyaExample) -> None:
    remove_output(case.path)
    compile_no_optimization(case)
    compile_with_level1_optimizations(case)
    compile_with_level2_optimizations(case)
    diff = check_for_diff(case.path)
    assert diff is None, f"Uncommitted changes were found:\n{diff}"
