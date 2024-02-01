import contextlib
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
from puya.errors import CodeError, Errors
from puya.options import PuyaOptions
from puya.parse import ParseResult, ParseSource, SourceLocation, get_parse_sources
from puya.utils import pushd

from tests import EXAMPLES_DIR, TEST_CASES_DIR, VCS_ROOT

APPROVAL_EXTENSIONS = ("*.teal", "*.awst", "*.ir", "application.json")
UNSTABLE_LOG_PREFIXES = {
    "debug": (
        "Building AWST for ",
        "Skipping puyapy stub ",
        "Skipping typeshed stub ",
        "Skipping stdlib stub ",
    ),
    "warning": ("Skipping stub: ",),
}


def _get_root_dir(path: Path) -> Path:
    if path.is_relative_to(EXAMPLES_DIR):
        return EXAMPLES_DIR
    if path.is_relative_to(TEST_CASES_DIR):
        return TEST_CASES_DIR
    return path if path.is_dir() else path.parent


@attrs.define(kw_only=True, str=False)
class Log:
    source_location: SourceLocation | None
    relative_path: Path | None
    event: str
    log_level: str

    @classmethod
    def parse(cls, log: structlog.typing.EventDict, root_dir: Path) -> "Log":
        relative_path: Path | None = None
        src_location: SourceLocation | None = None
        try:
            src_location = log["location"]
        except KeyError:
            pass
        else:
            assert isinstance(src_location, SourceLocation)
            relative_path = Path(src_location.file).resolve()
            with contextlib.suppress(ValueError):
                relative_path = relative_path.relative_to(root_dir)
        return Log(
            source_location=src_location,
            relative_path=relative_path,
            event=str(log["event"]),
            log_level=str(log["log_level"]),
        )

    def __str__(self) -> str:
        if self.source_location:
            col = f":{self.source_location.column + 1}" if self.source_location.column else ""
            location = f"{self.relative_path!s}:{self.source_location.line}{col} "
        else:
            location = ""
        return f"{location}{self.log_level}: {self.event}"


class _CompileCache(typing.NamedTuple):
    context: CompileContext
    module_awst: dict[str, Module]
    logs: list[Log]


@functools.cache
def _get_awst_cache(root_dir: Path) -> _CompileCache:
    # note that this caching assumes that AWST is the same across all
    # optimisation and debug levels, which is currently true.
    # if this were to no longer be true, this test speedup strategy would need to be revisited
    with pushd(root_dir), structlog.testing.capture_logs() as event_logs:
        context = parse_with_mypy(PuyaOptions(paths=[root_dir]))
        awst = transform_ast(context)
    return _CompileCache(context, awst, [Log.parse(x, root_dir) for x in event_logs])


def _normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _stabilise_logs(
    logs: list[Log], *, root_dir: Path, tmp_dir: Path, actual_path: Path
) -> Iterable[str]:
    root_dir = root_dir.resolve()
    actual_path = actual_path.resolve()
    normalized_vcs = _normalize_path(VCS_ROOT)
    normalized_tmp = _normalize_path(tmp_dir)
    normalized_root = _normalize_path(root_dir) + "/"
    actual_dir = actual_path if actual_path.is_dir() else actual_path.parent
    normalized_out = _normalize_path(actual_dir / "out")
    for log in logs:
        line = (
            str(log)
            .replace("\\", "/")
            .replace(normalized_tmp, normalized_out)
            .replace(normalized_root, "")
            .replace(normalized_vcs, "<git root>")
        )
        yield line


@attrs.define
class CompileContractResult:
    context: CompileContext
    module_awst: dict[str, Module]
    logs: str
    teal: dict[ParseSource, list[CompiledContract]]
    output_files: dict[str, str]


def narrow_sources(parse_result: ParseResult, src_path: Path) -> ParseResult:
    sources = get_parse_sources(
        [src_path], parse_result.manager.fscache, parse_result.manager.options
    )
    return attrs.evolve(parse_result, sources=sources)


def _filter_logs(logs: list[Log], root_dir: Path, src_path: Path) -> list[Log]:
    root_dir = root_dir.resolve()
    src_path = src_path.resolve()
    relative_src_root = src_path.relative_to(root_dir)
    result = []
    for log in logs:
        # ignore logs that come from files outside of src_path as these are
        # logs emitted during the cached AWST parsing step
        if log.relative_path and relative_src_root not in log.relative_path.parents:
            continue

        # ignore logs that are not output in a consistent order
        log_prefixes_to_ignore = UNSTABLE_LOG_PREFIXES.get(log.log_level)
        if log_prefixes_to_ignore and log.event.startswith(log_prefixes_to_ignore):
            continue

        result.append(log)
    return result


def _get_log_errors(logs: Iterable[Log]) -> str:
    return "\n".join(str(log) for log in logs if log.log_level == "error")


@functools.cache
def compile_src(
    src_path: Path, optimization_level: int, debug_level: int
) -> CompileContractResult:
    root_dir = _get_root_dir(src_path)
    context, awst, awst_logs = _get_awst_cache(root_dir)
    awst_logs = _filter_logs(awst_logs, root_dir, src_path)

    awst_errors = _get_log_errors(awst_logs)
    if awst_errors:
        raise CodeError(awst_errors)
    # create a new context from cache and specified src
    with tempfile.TemporaryDirectory() as tmp_dir_:
        tmp_dir = Path(tmp_dir_)
        context = attrs.evolve(
            context,
            errors=Errors(context.errors.read_source),
            parse_result=narrow_sources(context.parse_result, src_path),
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

        with pushd(root_dir), structlog.testing.capture_logs() as event_logs:
            teal = awst_to_teal(context, awst)
            if teal is None:
                raise CodeError(_get_log_errors(Log.parse(x, root_dir) for x in event_logs))
            write_teal_to_output(context, teal)

        output_files = {
            file.name: file.read_text("utf8")
            for ext in APPROVAL_EXTENSIONS
            for file in tmp_dir.rglob(ext)
        }
        logs = [Log.parse(x, root_dir) for x in event_logs]
        log_txt = "\n".join(
            _stabilise_logs(
                awst_logs + logs, root_dir=root_dir, tmp_dir=tmp_dir, actual_path=src_path
            )
        )
        return CompileContractResult(context, awst, log_txt, teal, output_files)
