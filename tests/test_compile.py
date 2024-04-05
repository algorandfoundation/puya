import os
import shutil
import subprocess
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path

import attrs
import pytest
from _pytest.mark import ParameterSet
from puya import log
from puya.options import PuyaOptions

from tests import EXAMPLES_DIR, TEST_CASES_DIR, VCS_ROOT
from tests.utils import APPROVAL_EXTENSIONS, CompilationResult, compile_src, get_relative_path

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}
SUFFIX_O0 = "_unoptimized"
SUFFIX_O1 = ""
SUFFIX_O2 = "_O2"


@attrs.frozen
class PuyaExample:
    root: Path
    name: str

    @property
    def path(self) -> Path:
        return self.root / self.name

    @property
    def id(self) -> str:
        return f"{self.root.stem}_{self.name}"


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
    test_case: PuyaExample, *, puya_options: PuyaOptions, write_logs: bool, suffix: str
) -> None:
    path = test_case.path
    if path.is_dir():
        dst_out_dir = path / ("out" + suffix)
    else:
        dst_out_dir = path.parent / f"{path.stem}_out{suffix}"

    puya_options.out_dir = dst_out_dir

    compile_result = compile_src(
        path,
        optimization_level=puya_options.optimization_level,
        debug_level=puya_options.debug_level,
    )

    dst_out_dir = puya_options.out_dir
    for output_path, output_content in compile_result.output_files.items():
        if _should_output(output_path, puya_options):
            file_out = dst_out_dir / output_path
            file_out.parent.mkdir(parents=True, exist_ok=True)
            file_out.write_text(output_content, "utf8")

    if write_logs:
        if path.is_dir():
            log_path = path / f"puya{suffix}.log"
        else:
            log_path = path.with_suffix(f".puya{suffix}.log")
        log_options = attrs.evolve(puya_options, out_dir=None, paths=(Path(test_case.name),))
        logs = "\n".join(
            (
                f"debug: {log_options}",
                *_stabilise_logs(
                    compile_result,
                ),
            )
        )
        log_path.write_text(logs, encoding="utf8")


def _normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _stabilise_logs(compiled_result: CompilationResult) -> Iterable[str]:
    root_dir = compiled_result.root_dir.resolve()
    actual_path = compiled_result.src_path.resolve()
    normalized_vcs = _normalize_path(VCS_ROOT)
    normalized_tmp = _normalize_path(compiled_result.tmp_dir)
    normalized_root = _normalize_path(root_dir) + "/"
    actual_dir = actual_path if actual_path.is_dir() else actual_path.parent
    normalized_out = _normalize_path(actual_dir / "out")
    return (
        _log_to_str(log_, root_dir)
        .replace("\\", "/")
        .replace(normalized_tmp, normalized_out)
        .replace(normalized_root, "")
        .replace(normalized_vcs, "<git root>")
        for log_ in compiled_result.logs
    )


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
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=0,
            output_teal=True,
            output_awst=False,
            output_destructured_ir=True,
            output_arc32=False,
        ),
        write_logs=False,
        suffix=SUFFIX_O0,
    )


def compile_with_level1_optimizations(test_case: PuyaExample) -> None:
    compile_test_case(
        test_case,
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=1,
            log_level=log.LogLevel.debug,
            output_teal=True,
            output_arc32=True,
            output_awst=True,
            output_ssa_ir=True,
            output_optimization_ir=True,
            output_destructured_ir=True,
            output_memory_ir=True,
            output_client=True,
        ),
        write_logs=True,
        suffix=SUFFIX_O1,
    )


def compile_with_level2_optimizations(test_case: PuyaExample) -> None:
    compile_test_case(
        test_case,
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=2,
            debug_level=0,
            output_teal=True,
            output_arc32=False,
            output_destructured_ir=True,
            log_level=log.LogLevel.debug,
            output_optimization_ir=False,
        ),
        write_logs=False,
        suffix=SUFFIX_O2,
    )


def get_test_cases() -> Iterable[ParameterSet]:
    all_examples = [
        PuyaExample(root, item.name)
        for root in (EXAMPLES_DIR, TEST_CASES_DIR)
        for item in root.iterdir()
        if item.is_dir() and any(item.glob("*.py"))
    ]
    for example in all_examples:
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
