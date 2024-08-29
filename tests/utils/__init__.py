import functools
import typing
from collections.abc import Iterable, Sequence
from pathlib import Path

import attrs
from puya.awst.nodes import (
    AWST,
    Subroutine as AWSTSubroutine,
)
from puya.compile import awst_to_teal, write_artifacts
from puya.context import CompileContext
from puya.errors import CodeError
from puya.log import Log, LogLevel, logging_context
from puya.models import CompilationArtifact
from puya.options import PuyaOptions
from puya.parse import CompileSource, SourceLocation
from puya.utils import pushd
from puyapy.awst_build.main import transform_ast
from puyapy.compile import parse_with_mypy
from puyapy.parse import ParseResult

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
    parse_result: ParseResult
    module_awst: AWST
    embedded_funcs: Sequence[AWSTSubroutine]
    logs: list[Log]


@functools.cache
def get_awst_cache(root_dir: Path) -> _CompileCache:
    # note that this caching assumes that AWST is the same across all
    # optimisation and debug levels, which is currently true.
    # if this were to no longer be true, this test speedup strategy would need to be revisited
    with pushd(root_dir), logging_context() as log_ctx:
        context = parse_with_mypy(PuyaOptions(paths=[root_dir]))
        awst, embedded_funcs = transform_ast(context)
    return _CompileCache(context, context.parse_result, awst, embedded_funcs, log_ctx.logs)


@attrs.frozen(kw_only=True)
class CompilationResult:
    context: CompileContext
    module_awst: AWST
    logs: list[Log]
    teal: list[CompilationArtifact]
    src_path: Path
    """original source path"""
    root_dir: Path
    """examples or test_cases path"""


def narrow_sources(sources: Sequence[CompileSource], src_path: Path) -> Sequence[CompileSource]:
    return [
        src
        for src in sources
        if src_path.resolve() in (src.path.resolve(), *src.path.resolve().parents)
    ]


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
    try:
        return location.file.relative_to(root_dir)
    except ValueError:
        return None


def _get_log_errors(logs: Iterable[Log]) -> str:
    return "\n".join(str(log) for log in logs if log.level == LogLevel.error)


def compile_src(path: Path, *, optimization_level: int, debug_level: int) -> CompilationResult:
    return compile_src_from_options(
        PuyaOptions(
            paths=(path,),
            optimization_level=optimization_level,
            debug_level=debug_level,
            output_arc32=False,
            output_teal=False,
        )
    )


def compile_src_from_options(options: PuyaOptions) -> CompilationResult:
    (src_path,) = options.paths
    root_dir = _get_root_dir(src_path)
    context, parse_result, awst, embedded_funcs, awst_logs = get_awst_cache(root_dir)
    awst_logs = _filter_logs(awst_logs, root_dir, src_path)

    awst_errors = _get_log_errors(awst_logs)
    if awst_errors:
        raise CodeError(awst_errors)
    # create a new context from cache and specified src
    with logging_context() as log_ctx:
        context = attrs.evolve(
            context,
            options=options,
            sources=narrow_sources(context.sources, src_path),
        )

        with pushd(root_dir):
            try:
                teal = awst_to_teal(log_ctx, context, awst, embedded_funcs)
            except SystemExit as ex:
                raise CodeError(_get_log_errors(log_ctx.logs)) from ex

            write_artifacts(context, teal)

        return CompilationResult(
            context=context,
            module_awst=awst,
            logs=awst_logs + log_ctx.logs,
            teal=teal,
            root_dir=root_dir,
            src_path=src_path,
        )


@attrs.frozen
class PuyaExample:
    root: Path
    name: str

    @property
    def path(self) -> Path:
        return self.root / self.name

    @property
    def template_vars_path(self) -> Path | None:
        template_vars_path = self.path / "template.vars"
        return template_vars_path.resolve() if template_vars_path.exists() else None

    @property
    def id(self) -> str:
        return f"{self.root.stem}_{self.name}"


def get_all_examples() -> list[PuyaExample]:
    return [
        PuyaExample(root, item.name)
        for root in (EXAMPLES_DIR, TEST_CASES_DIR)
        for item in root.iterdir()
        if item.is_dir() and any(item.glob("*.py"))
    ]


def load_template_vars(path: Path | None) -> tuple[str, list[str]]:
    result = []
    prefix = "TMPL_"
    if path is not None:
        for line in path.read_text("utf8").splitlines():
            var, value_str = line.split("=", maxsplit=1)
            if var == "prefix":
                prefix = value_str
            else:
                result.append(line)
    return prefix, result
