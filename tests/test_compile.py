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
from puya.parse import EMBEDDED_MODULES

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


@attrs.define
class CompilationResult:
    rel_path: str


def rename_file(file_name: str, suffix: str | None) -> str:
    if suffix:
        if file_name.endswith(".destructured.ir"):
            final_ir_path = Path(file_name)
            suffix_keep, _ = final_ir_path.suffixes
            move_to = final_ir_path.with_suffix("").with_suffix(f"{suffix_keep}{suffix}.ir")
            return move_to.name
        elif file_name.endswith(".teal"):
            teal_path = Path(file_name)
            program, *other_suffixes = teal_path.suffixes
            new_suffix = "".join((f"{program}{suffix}", *other_suffixes))
            old_suffix = "".join(teal_path.suffixes)
            new_stem = Path(file_name[: -len(old_suffix)])
            return new_stem.with_suffix(new_suffix).name
    return file_name


def _should_output(file_name: str, puya_options: PuyaOptions) -> bool:
    for pattern, include_in_output in {
        "*.teal": puya_options.output_teal,
        "application.json": puya_options.output_arc32,
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
    suffix: str = "",
) -> None:
    path = test_case.path
    dst_out_dir = (path if path.is_dir() else path.parent) / "out"
    puya_options.out_dir = dst_out_dir

    compile_result = compile_src(test_case.path, puya_options.optimization_level, 1)
    context = compile_result.context
    # TODO: include this in compile_src
    if puya_options.output_awst:
        sources = tuple(str(s.path) for s in context.parse_result.sources)
        for module_name, module in compile_result.module_awst.items():
            if module_name in EMBEDDED_MODULES:
                continue
            if module.source_file_path.startswith(sources):
                output_awst(module, puya_options)
    dst_out_dir = puya_options.out_dir

    for file_name, file_content in compile_result.output_files.items():
        if not _should_output(file_name, puya_options):
            continue

        file_name = rename_file(file_name, suffix)
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


def compile_no_optimization(test_case: PuyaExample) -> None:
    compile_test_case(
        test_case,
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=0,
            output_teal=True,
            output_awst=True,
            output_destructured_ir=True,
            output_arc32=False,
        ),
        write_logs=False,
        suffix="_unoptimized",
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
            output_awst=False,
            output_ssa_ir=True,
            output_optimization_ir=True,
            output_destructured_ir=True,
            output_memory_ir=True,
        ),
        write_logs=True,
    )


def compile_with_level2_optimizations(test_case: PuyaExample) -> None:
    compile_test_case(
        test_case,
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=2,
            output_teal=True,
            output_arc32=True,
            output_destructured_ir=True,
            log_level=LogLevel.debug,
            output_optimization_ir=False,
        ),
        write_logs=False,
        suffix="_O2",
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
        for f in path.rglob(f"**/out/{file}"):
            if f.is_file():
                f.unlink()


def check_for_diff(path: Path) -> str | None:
    git = shutil.which("git")
    assert git is not None, "could not find git"
    if path.is_dir():
        paths = [path]
    else:
        paths = [path, path.parent / "out", path.with_suffix(".puya.log")]
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
