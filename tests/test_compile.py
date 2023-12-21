import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

import attrs
import pytest
import structlog
from puya.compile import awst_to_teal, write_teal_to_output
from puya.options import PuyaOptions

from tests.conftest import parse_src_to_awst

ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
    "PYTHONUTF8": "1",  # force utf8 on windows
}
SCRIPT_DIR = Path(__file__).parent
GIT_ROOT = SCRIPT_DIR.parent
CONTRACT_ROOT_DIRS = [
    GIT_ROOT / "examples",
    GIT_ROOT / "test_cases",
]
APPROVED_EXTENSIONS = ("*.teal", "*.awst", "*.ir")


@attrs.define(str=False)
class PuyaExample:
    root: Path
    path: Path

    def __str__(self) -> str:
        return f"{self.root.stem}_{self.path.stem}"


@attrs.define
class CompilationResult:
    rel_path: str


def _stabilise_logs(stdout: str) -> list[str]:
    return [
        line.replace("\\", "/").replace(str(GIT_ROOT).replace("\\", "/"), "<git root>")
        for line in stdout.splitlines()
        if not line.startswith(
            (
                "debug: Skipping puyapy stub ",
                "debug: Skipping typeshed stub ",
                "warning: Skipping stub: ",
                "debug: Skipping stdlib stub ",
            )
        )
    ]



def move_with_suffix(
    src_dir: Path,
    dst_dir: Path,
    suffix: str,
) -> None:
    final_ir = list(src_dir.rglob("*.final.ir"))
    final_ir += list(src_dir.rglob("*.final_pr.ir"))
    teal_files = list(src_dir.rglob("*.teal"))

    moved_teal = list[Path]()
    for teal_path in teal_files:
        program, *other_suffixes = teal_path.suffixes
        new_suffix = "".join((f"{program}{suffix}", *other_suffixes))
        old_suffix = "".join(teal_path.suffixes)
        new_stem = str(teal_path.name)[: -len(old_suffix)]
        move_to = (dst_dir.parent / new_stem).with_suffix(new_suffix)
        teal_path.rename(move_to)
        moved_teal.append(move_to)
    moved_ir = list[Path]()
    for final_ir_path in final_ir:
        suffix_keep, _ = final_ir_path.suffixes
        new_stem = final_ir_path.with_suffix("").with_suffix(f"{suffix_keep}{suffix}.ir").stem
        move_to = dst_dir.parent / new_stem
        final_ir_path.rename(move_to)
        moved_ir.append(move_to)

def checked_compile(
    test_case: PuyaExample, *, puya_options: PuyaOptions, write_logs: bool, suffix: str,
) -> None:
    path = test_case.path

    compile_cache = parse_src_to_awst(path)
    context = compile_cache.context
    awst = compile_cache.module_awst
    with structlog.testing.capture_logs() as logs, tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        context = attrs.evolve(
            context,
            options=attrs.evolve(puya_options, out_dir=tmp_dir, debug_level=1),
        )

        teal = awst_to_teal(context, awst)
        write_teal_to_output(context, teal)
        dst_dir = (path if path.is_dir() else path.parent) / "out"
        move_with_suffix(tmp_dir, dst_dir, suffix)

        if write_logs:
            if path.is_dir():
                log_path = path / "puya.log"
            else:
                log_path = path.with_suffix(".puya.log")

            log_txt = "\n".join(
                [
                    ">> " + " ".join(cmd),
                    *_stabilise_logs(result.stdout),
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
            output_arc32=False,
            output_awst=True,
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
            output_arc32=False,
            output_awst=False,
            output_ssa_ir=True,
            output_optimization_ir=True,
            output_cssa_ir=True,
            output_post_ssa_ir=True,
            output_parallel_copies_ir=True,
            output_final_ir=True,
        ),
        write_logs=False,  # TODO
        suffix="",
    )


def compile_with_level2_optimizations(test_case: PuyaExample) -> None:
    checked_compile(
        test_case,
        puya_options=PuyaOptions(
            paths=[test_case.path],
            optimization_level=2,
            output_teal=True,
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
    for file in APPROVED_EXTENSIONS:
        for f in path.rglob(f"**/out/{file}"):
            if f.is_file():
                f.unlink()


def check_for_diff(path: Path) -> str | None:
    git = shutil.which("git")
    assert git is not None, "could not find git"
    result = subprocess.run([git, "status", "-s", str(path)], check=True, capture_output=True)
    stdout = result.stdout.decode("utf8")
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
