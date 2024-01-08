import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

import attrs
import pytest
import structlog
from puya.awst_build.main import output_awst
from puya.compile import awst_to_teal, write_teal_to_output
from puya.options import PuyaOptions
from puya.parse import EMBEDDED_MODULES, SourceLocation

from tests.conftest import parse_src_to_awst

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}
SCRIPT_DIR = Path(__file__).parent
VCS_DIR = SCRIPT_DIR.parent
CONTRACT_ROOT_DIRS = [
    VCS_DIR / "examples",
    VCS_DIR / "test_cases",
]
APPROVAL_EXTENSIONS = ("*.teal", "*.awst", "*.ir")


@attrs.define(str=False)
class PuyaExample:
    root: Path
    path: Path

    def __str__(self) -> str:
        return f"{self.root.stem}_{self.path.stem}"


@attrs.define
class CompilationResult:
    rel_path: str


def _normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _stabilise_logs(
    logs: list[structlog.typing.EventDict], root_dir: Path, tmp_dir: Path, actual_path: Path
) -> Iterable[str]:
    normalized_vcs = _normalize_path(VCS_DIR)
    normalized_tmp = _normalize_path(tmp_dir)
    normalized_root = _normalize_path(root_dir) + "/"
    actual_dir = actual_path if actual_path.is_dir() else actual_path.parent
    normalized_out = _normalize_path(actual_dir / "out")
    normalized_relative = _normalize_path(actual_path.relative_to(root_dir))
    for log in logs:
        location = ""
        try:
            src_location = log["location"]
            assert isinstance(src_location, SourceLocation)
            path = Path(src_location.file)
            location = str(path.relative_to(root_dir))
            if not location.startswith(normalized_relative):
                continue
            location = f"{location}:{src_location.line} "
        except KeyError:
            pass
        msg: str = log["event"]
        line = f"{location}{log['log_level']}: {msg}"
        line = line.replace("\\", "/")
        line = line.replace(normalized_tmp, normalized_out)
        line = line.replace(normalized_root, "")
        line = line.replace(normalized_vcs, "<git root>")

        if not line.startswith(
            (
                "debug: Building AWST for ",
                "debug: Skipping puyapy stub ",
                "debug: Skipping typeshed stub ",
                "warning: Skipping stub: ",
                "debug: Skipping stdlib stub ",
            )
        ):
            yield line


def rename_file(file_name: str, suffix: str | None) -> str:
    if suffix:
        if file_name.endswith((".final.ir", ".final_par.ir")):
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


def format_options_as_cmd(path: Path, puya_options: PuyaOptions) -> str:
    values = attrs.asdict(puya_options, recurse=False)
    values["out_dir"] = "out"
    values["log_level"] = "debug"

    flags = [f"-O{values['optimization_level']}"]
    flags += [
        f"--{f.replace('_', '-')}"
        for f in (
            "output_ssa_ir",
            "output_optimization_ir",
            "output_final_ir",
            "output_cssa_ir",
            "output_post_ssa_ir",
            "output_parallel_copies_ir",
        )
        if values.get(f)
    ]
    flags += [
        f"--{f.replace('_', '-')}={values[f]}" for f in ("out_dir", "debug_level", "log_level")
    ]
    options_str = " ".join(flags)

    return f">> poetry run puyapy {options_str} {path}"


def checked_compile(
    test_case: PuyaExample,
    *,
    puya_options: PuyaOptions,
    write_logs: bool,
    suffix: str | None = None,
) -> None:
    path = test_case.path
    root_dir = test_case.root
    rel_path = path.relative_to(root_dir)

    compile_cache = parse_src_to_awst(path)
    context = compile_cache.context
    awst = compile_cache.module_awst
    cached_logs = compile_cache.logs
    with structlog.testing.capture_logs() as logs, tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        context = attrs.evolve(
            context,
            options=attrs.evolve(puya_options, out_dir=tmp_dir, debug_level=1),
        )
        if context.options.output_awst:
            sources = tuple(str(s.path) for s in context.parse_result.sources)
            for module_name, module in awst.items():
                if module_name in EMBEDDED_MODULES:
                    continue
                if module.source_file_path.startswith(sources):
                    output_awst(module, context.options)
        teal = awst_to_teal(context, awst)
        write_teal_to_output(context, teal)
        dst_dir = path if path.is_dir() else path.parent
        dst_out_dir = dst_dir / "out"
        for ext in APPROVAL_EXTENSIONS:
            for file in tmp_dir.rglob(ext):
                file_name = rename_file(file.name, suffix)
                relative_dir = file.relative_to(tmp_dir).parent
                file_dest_dir = dst_out_dir / relative_dir
                file_dest_dir.mkdir(parents=True, exist_ok=True)
                file.rename(file_dest_dir / file_name)

        if write_logs:
            if path.is_dir():
                log_path = path / "puya.log"
            else:
                log_path = path.with_suffix(".puya.log")

            log_txt = "\n".join(
                [
                    format_options_as_cmd(rel_path, context.options),
                    *_stabilise_logs(cached_logs + logs, root_dir, tmp_dir, path),
                    ">> exit code = 0",  # TODO: remove this
                ]
            )
            log_path.write_text(log_txt, encoding="utf8")


def compile_no_optimization(test_case: PuyaExample) -> None:
    checked_compile(
        test_case,
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=0,
            output_teal=True,
            output_awst=True,
            output_final_ir=True,
            output_arc32=False,
        ),
        write_logs=False,
        suffix="_unoptimized",
    )


def compile_with_level1_optimizations(test_case: PuyaExample) -> None:
    checked_compile(
        test_case,
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=1,
            output_teal=True,
            output_arc32=True,
            output_awst=False,
            output_ssa_ir=True,
            output_optimization_ir=True,
            output_cssa_ir=True,
            output_post_ssa_ir=True,
            output_parallel_copies_ir=True,
            output_final_ir=True,
        ),
        write_logs=True,
    )


def compile_with_level2_optimizations(test_case: PuyaExample) -> None:
    checked_compile(
        test_case,
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=2,
            output_teal=True,
            output_arc32=False,
        ),
        write_logs=False,
        suffix="_O2",
    )


def get_test_cases() -> Iterable[PuyaExample]:
    to_compile = []
    for root in CONTRACT_ROOT_DIRS:
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
            [git, "status", "-s", str(path)], check=True, capture_output=True, cwd=VCS_DIR
        )
        stdout += result.stdout.decode("utf8")
    return stdout or None


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    metafunc.parametrize("case", get_test_cases(), ids=str)


def test_cases(case: PuyaExample) -> None:
    remove_output(case.path)
    compile_no_optimization(case)
    compile_with_level1_optimizations(case)
    diff = check_for_diff(case.path)
    assert diff is None, f"Uncommitted changes were found:\n{diff}"
