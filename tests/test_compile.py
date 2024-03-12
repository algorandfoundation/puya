import os
import shutil
import subprocess
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path

import attrs
import pytest
from puya.awst_build.main import output_awst
from puya.logging_config import LogLevel
from puya.options import PuyaOptions

from tests import EXAMPLES_DIR, TEST_CASES_DIR, VCS_ROOT
from tests.utils import APPROVAL_EXTENSIONS, compile_src

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}


@attrs.define(str=False)
class PuyaExample:
    root: Path
    path: Path

    def __str__(self) -> str:
        return f"{self.root.stem}_{self.path.stem}"


def _should_output(file_name: str, puya_options: PuyaOptions) -> bool:
    for pattern, include_in_output in {
        "*.teal": puya_options.output_teal,
        "*.arc32.json": puya_options.output_arc32,
        "*.awst": puya_options.output_awst,
        "*.ssa.ir": puya_options.output_ssa_ir,
        "*.ssa.opt_pass_*.ir": puya_options.output_optimization_ir,
        "*.destructured.ir": puya_options.output_destructured_ir,
        "*.mir": puya_options.output_memory_ir,
    }.items():
        if include_in_output and fnmatch(file_name, pattern):
            return True
    return False


def compile_test_case(
    test_case: PuyaExample,
    *,
    puya_options: PuyaOptions,
    write_logs: bool,
    suffix: str,
) -> None:
    path = test_case.path
    if path.is_dir():
        dst_out_dir = path / ("out" + suffix)
    else:
        dst_out_dir = path.parent / f"{path.stem}_out{suffix}"

    puya_options.out_dir = dst_out_dir

    compile_result = compile_src(
        test_case.path,
        optimization_level=puya_options.optimization_level,
        debug_level=puya_options.debug_level,
    )
    context = compile_result.context
    # TODO: include this in compile_src
    if puya_options.output_awst:
        sources = tuple(str(s.path) for s in context.parse_result.sources)
        for module in compile_result.module_awst.values():
            if module.source_file_path.startswith(sources):
                output_awst(module, puya_options)

    dst_out_dir = puya_options.out_dir
    for file_name, file_content in compile_result.output_files.items():
        if _should_output(file_name, puya_options):
            file_out = dst_out_dir / file_name
            dst_out_dir.mkdir(parents=True, exist_ok=True)
            file_out.write_text(file_content, "utf8")

    if write_logs:
        if path.is_dir():
            log_path = path / f"puya{suffix}.log"
        else:
            log_path = path.with_suffix(f".puya{suffix}.log")
        log_options = attrs.evolve(
            puya_options, out_dir=None, paths=(test_case.path.relative_to(test_case.root),)
        )
        log_path.write_text(f"debug: {log_options}\n{compile_result.logs}", encoding="utf8")


SUFFIX_O0 = "_unoptimized"
SUFFIX_O1 = ""
SUFFIX_O2 = "_O2"


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
            log_level=LogLevel.debug,
            output_teal=True,
            output_arc32=True,
            output_awst=True,
            output_ssa_ir=True,
            output_optimization_ir=True,
            output_destructured_ir=True,
            output_memory_ir=True,
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
            log_level=LogLevel.debug,
            output_optimization_ir=False,
        ),
        write_logs=False,
        suffix=SUFFIX_O2,
    )


def get_test_cases() -> Iterable[PuyaExample]:
    to_compile = []
    for root in (EXAMPLES_DIR, TEST_CASES_DIR):
        for item in root.iterdir():
            if item.is_dir():
                if any(item.rglob("*.py")):
                    yield PuyaExample(root, item)
                    to_compile.append(item)
            elif item.is_file() and item.suffix == ".py" and item.name != "__init__.py":
                yield PuyaExample(root, item)


def remove_output(path: Path) -> None:
    for file in APPROVAL_EXTENSIONS:
        for out_suffix in (SUFFIX_O0, SUFFIX_O1, SUFFIX_O2):
            for f in path.rglob(f"**/*out{out_suffix}/{file}"):
                if f.is_file():
                    f.unlink()


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
            [git, "diff", str(path)], check=True, capture_output=True, cwd=VCS_ROOT
        )
        stdout += result.stdout.decode("utf8")
    return stdout or None


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    metafunc.parametrize("case", get_test_cases(), ids=str)


def test_cases(case: PuyaExample) -> None:
    remove_output(case.path)
    compile_no_optimization(case)
    compile_with_level1_optimizations(case)
    compile_with_level2_optimizations(case)
    diff = check_for_diff(case.path)
    assert diff is None, f"Uncommitted changes were found:\n{diff}"
