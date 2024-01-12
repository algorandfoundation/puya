import functools
import tempfile
import typing
from pathlib import Path
from typing import Iterable

import attrs
import structlog.testing
import structlog.typing
from puya.awst.nodes import Module
from puya.awst_build.main import transform_ast
from puya.codegen.emitprogram import CompiledContract
from puya.compile import awst_to_teal, parse_with_mypy, write_teal_to_output
from puya.context import CompileContext
from puya.errors import Errors
from puya.options import PuyaOptions
from puya.parse import ParseResult, ParseSource, SourceLocation, get_parse_sources
from puya.utils import pushd

from tests import EXAMPLES_DIR, TEST_CASES_DIR, VCS_ROOT

APPROVAL_EXTENSIONS = ("*.teal", "*.awst", "*.ir")


def _get_root_dir(path: Path) -> Path:
    if path.is_relative_to(EXAMPLES_DIR):
        return EXAMPLES_DIR
    if path.is_relative_to(TEST_CASES_DIR):
        return TEST_CASES_DIR
    return path if path.is_dir() else path.parent


class _CompileCache(typing.NamedTuple):
    context: CompileContext
    module_awst: dict[str, Module]
    logs: list[structlog.typing.EventDict]


@functools.cache
def _get_awst_cache(root_dir: Path) -> _CompileCache:
    # note that this caching assumes that AWST is the same across all
    # optimisation and debug levels, which is currently true.
    # if this were to no longer be true, this test speedup strategy would need to be revisited
    with pushd(root_dir), structlog.testing.capture_logs() as logs:
        context = parse_with_mypy(PuyaOptions(paths=[root_dir]))
        awst = transform_ast(context)
    return _CompileCache(context, awst, logs)


def _normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _stabilise_logs(
    logs: list[structlog.typing.EventDict], *, root_dir: Path, tmp_dir: Path, actual_path: Path
) -> Iterable[str]:
    normalized_vcs = _normalize_path(VCS_ROOT)
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
            if not path.is_relative_to(root_dir):
                continue
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


@attrs.define
class CompileContractResult:
    context: CompileContext
    module_awst: dict[str, Module]
    logs: str
    teal: dict[ParseSource, list[CompiledContract]]
    output_files: dict[str, str]


def _narrow_sources(parse_result: ParseResult, src_path: Path) -> ParseResult:
    sources = get_parse_sources(
        [src_path], parse_result.manager.fscache, parse_result.manager.options
    )
    return attrs.evolve(parse_result, sources=sources)


@functools.cache
def compile_src(
    src_path: Path, optimization_level: int, debug_level: int
) -> CompileContractResult:
    root_dir = _get_root_dir(src_path)
    context, awst, awst_logs = _get_awst_cache(root_dir)
    # create a new context from cache and specified src
    with tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        context = attrs.evolve(
            context,
            errors=Errors(),
            parse_result=_narrow_sources(context.parse_result, src_path),
            options=PuyaOptions(
                paths=(src_path,),
                optimization_level=optimization_level,
                debug_level=debug_level,
                output_teal=True,
                output_awst=True,
                output_final_ir=True,
                output_arc32=True,
                output_ssa_ir=True,
                output_optimization_ir=True,
                output_cssa_ir=True,
                output_post_ssa_ir=True,
                output_parallel_copies_ir=True,
                out_dir=tmp_dir,
            ),
        )

        with pushd(root_dir), structlog.testing.capture_logs() as logs:
            teal = awst_to_teal(context, awst)
            assert teal is not None, f"compilation failed: {src_path} at O{optimization_level}"
            write_teal_to_output(context, teal)

        output_files = {
            file.name: file.read_text("utf8")
            for ext in APPROVAL_EXTENSIONS
            for file in tmp_dir.rglob(ext)
        }
        log_txt = "\n".join(
            _stabilise_logs(
                awst_logs + logs, root_dir=root_dir, tmp_dir=tmp_dir, actual_path=src_path
            )
        )
        return CompileContractResult(context, awst, log_txt, teal, output_files)
