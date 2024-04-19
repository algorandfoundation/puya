import functools
import tempfile
import typing
from collections.abc import Iterable
from pathlib import Path

import attrs
from puya.awst.nodes import Module
from puya.awst_build.main import output_awst, transform_ast
from puya.compile import (
    module_irs_to_teal,
    optimize_and_destructure_module_irs,
    parse_with_mypy,
    write_artifacts,
)
from puya.context import CompileContext
from puya.errors import CodeError
from puya.ir.main import build_module_irs
from puya.log import Log, LoggingContext, LogLevel, logging_context
from puya.models import CompilationArtifact
from puya.options import PuyaOptions
from puya.parse import ParseResult, ParseSource, SourceLocation, get_parse_sources
from puya.utils import pushd

from tests import EXAMPLES_DIR, TEST_CASES_DIR

APPROVAL_EXTENSIONS = frozenset((".teal", ".awst", ".ir", ".mir", ".arc32.json"))
UNSTABLE_LOG_PREFIXES = {
    LogLevel.debug: (
        "Building AWST for ",
        "Skipping algopy stub ",
        "Skipping typeshed stub ",
        "Skipping stdlib stub ",
        "Discovered user module ",
        # ignore platform specific paths
        "Using python executable: ",
        "Using python site-packages: ",
        "Found algopy: ",
    ),
}


def _get_root_dir(path: Path) -> Path:
    if path.is_relative_to(EXAMPLES_DIR):
        return EXAMPLES_DIR
    if path.is_relative_to(TEST_CASES_DIR):
        return TEST_CASES_DIR
    return path if path.is_dir() else path.parent


class _CompileCache(typing.NamedTuple):
    context: CompileContext
    module_awst: dict[str, Module]
    logs: list[Log]


@functools.cache
def get_awst_cache(root_dir: Path) -> _CompileCache:
    # note that this caching assumes that AWST is the same across all
    # optimisation and debug levels, which is currently true.
    # if this were to no longer be true, this test speedup strategy would need to be revisited
    with pushd(root_dir), logging_context() as log_ctx:
        context = parse_with_mypy(PuyaOptions(paths=[root_dir]))
        awst = transform_ast(context)
    return _CompileCache(context, awst, log_ctx.logs)


@attrs.frozen(kw_only=True)
class CompilationResult:
    context: CompileContext
    module_awst: dict[str, Module]
    logs: list[Log]
    teal: dict[ParseSource, list[CompilationArtifact]]
    output_files: dict[Path, str]
    src_path: Path
    """original source path"""
    root_dir: Path
    """examples or test_cases path"""
    tmp_dir: Path
    """tmp path used during compilation"""


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
        relative_path = get_relative_path(log.location, root_dir)
        if relative_path and relative_src_root not in (
            relative_path,
            *relative_path.parents,
        ):
            continue

        # ignore logs that are not output in a consistent order
        log_prefixes_to_ignore = UNSTABLE_LOG_PREFIXES.get(log.level)
        if log_prefixes_to_ignore and log.message.startswith(log_prefixes_to_ignore):
            continue

        result.append(log)
    return result


def get_relative_path(location: SourceLocation | None, root_dir: Path) -> Path | None:
    if not location:
        return None
    relative_path = Path(location.file).resolve()
    try:
        return relative_path.relative_to(root_dir)
    except ValueError:
        return None


def _get_log_errors(logs: Iterable[Log]) -> str:
    return "\n".join(str(log) for log in logs if log.level == LogLevel.error)


def awst_to_teal(
    log_ctx: LoggingContext,
    context: CompileContext,
    module_asts: dict[str, Module],
) -> dict[ParseSource, list[CompilationArtifact]] | None:
    if log_ctx.num_errors:
        return None
    module_irs = build_module_irs(context, module_asts)
    if log_ctx.num_errors:
        return None
    module_irs_destructured = optimize_and_destructure_module_irs(context, module_irs)
    if log_ctx.num_errors:
        return None
    compiled_contracts = module_irs_to_teal(context, module_irs_destructured)
    if log_ctx.num_errors:
        return None
    return compiled_contracts


@functools.cache
def compile_src(src_path: Path, optimization_level: int, debug_level: int) -> CompilationResult:
    root_dir = _get_root_dir(src_path)
    context, awst, awst_logs = get_awst_cache(root_dir)
    awst_logs = _filter_logs(awst_logs, root_dir, src_path)

    awst_errors = _get_log_errors(awst_logs)
    if awst_errors:
        raise CodeError(awst_errors)
    # create a new context from cache and specified src
    with tempfile.TemporaryDirectory() as tmp_dir_, logging_context() as log_ctx:
        tmp_dir = Path(tmp_dir_)
        context = attrs.evolve(
            context,
            parse_result=narrow_sources(context.parse_result, src_path),
            options=PuyaOptions(
                paths=(src_path,),
                optimization_level=optimization_level,
                debug_level=debug_level,
                output_teal=True,
                output_awst=True,
                output_destructured_ir=True,
                output_arc32=True,
                output_ssa_ir=optimization_level < 2,
                output_optimization_ir=optimization_level < 2,
                output_memory_ir=True,
                output_client=True,
                out_dir=tmp_dir,
            ),
        )

        with pushd(root_dir):
            # write AWST
            sources = tuple(str(s.path) for s in context.parse_result.sources)
            for module in awst.values():
                if module.source_file_path.startswith(sources):
                    output_awst(module, context.options)

            teal = awst_to_teal(log_ctx, context, awst)
            if teal is None:
                raise CodeError(_get_log_errors(log_ctx.logs))

            write_artifacts(context, teal)

        output_files = {
            file.relative_to(tmp_dir): file.read_text("utf8")
            for file in tmp_dir.iterdir()
            if file.suffix in APPROVAL_EXTENSIONS
        }
        return CompilationResult(
            context=context,
            module_awst=awst,
            logs=awst_logs + log_ctx.logs,
            teal=teal,
            output_files=output_files,
            tmp_dir=tmp_dir,
            root_dir=root_dir,
            src_path=src_path,
        )
