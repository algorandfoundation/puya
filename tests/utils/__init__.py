import functools
import typing
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import Path

import attrs

from puya.awst import nodes as awst_nodes
from puya.compile import awst_to_teal
from puya.errors import CodeError
from puya.log import Log, LogLevel, logging_context
from puya.models import CompilationArtifact, ContractReference, LogicSigReference
from puya.parse import SourceLocation
from puya.utils import pushd
from puyapy.awst_build.main import transform_ast
from puyapy.compile import output_awst, parse_with_mypy, write_arc4_clients
from puyapy.options import PuyaPyOptions
from puyapy.parse import ParseResult, SourceDiscoveryMechanism
from puyapy.template import parse_template_key_value
from puyapy.utils import determine_out_dir
from tests import EXAMPLES_DIR, TEST_CASES_DIR

APPROVAL_EXTENSIONS = frozenset((".teal", ".awst", ".ir", ".mir", ".arc32.json", ".arc56.json"))
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
    parse_result: ParseResult
    module_awst: awst_nodes.AWST
    compilation_set: Sequence[ContractReference | LogicSigReference]
    logs: list[Log]


@functools.cache
def get_awst_cache(root_dir: Path) -> _CompileCache:
    # note that this caching assumes that AWST is the same across all
    # optimisation and debug levels, which is currently true.
    # if this were to no longer be true, this test speedup strategy would need to be revisited
    with pushd(root_dir), logging_context() as log_ctx:
        parse_result = parse_with_mypy([root_dir])
        awst, compilation_set = transform_ast(parse_result)
    return _CompileCache(parse_result, awst, compilation_set, log_ctx.logs)


@attrs.frozen(kw_only=True)
class CompilationResult:
    module_awst: awst_nodes.AWST
    logs: list[Log]
    teal: list[CompilationArtifact]
    src_path: Path
    """original source path"""
    root_dir: Path
    """examples or test_cases path"""


def narrowed_parse_result(parse_result: ParseResult, src_path: Path) -> ParseResult:
    filtered_ordered_modules = {
        name: sm
        for name, sm in parse_result.ordered_modules.items()
        if sm.path.resolve().is_relative_to(src_path.resolve())
        or sm.discovery_mechanism == SourceDiscoveryMechanism.dependency
    }
    return ParseResult(
        mypy_options=parse_result.mypy_options,
        ordered_modules=filtered_ordered_modules,
    )


def narrowed_compile_context(
    parse_result: ParseResult,
    src_path: Path,
    awst: awst_nodes.AWST,
    compilation_set: Collection[ContractReference | LogicSigReference],
    puyapy_options: PuyaPyOptions,
) -> tuple[
    Mapping[Path, Sequence[str] | None], Mapping[ContractReference | LogicSigReference, Path]
]:
    narrowed_sources_by_path = {
        sm.path: sm.lines
        for sm in parse_result.ordered_modules.values()
        if sm.path.resolve().is_relative_to(src_path.resolve())
        and sm.discovery_mechanism != SourceDiscoveryMechanism.dependency
    }
    awst_lookup = {n.id: n for n in awst}
    compilation_set = {
        target_id: determine_out_dir(loc.file.parent, puyapy_options)
        for target_id, loc in ((t, awst_lookup[t].source_location) for t in compilation_set)
        if loc.file in narrowed_sources_by_path
    }
    return narrowed_sources_by_path, compilation_set


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
    if not location or not location.file:
        return None
    try:
        return location.file.relative_to(root_dir)
    except ValueError:
        return None


def _get_log_errors(logs: Iterable[Log]) -> str:
    return "\n".join(str(log) for log in logs if log.level == LogLevel.error)


def compile_src(path: Path, *, optimization_level: int, debug_level: int) -> CompilationResult:
    return compile_src_from_options(
        PuyaPyOptions(
            paths=(path,),
            optimization_level=optimization_level,
            debug_level=debug_level,
        )
    )


def compile_src_from_options(options: PuyaPyOptions) -> CompilationResult:
    (src_path,) = options.paths
    root_dir = _get_root_dir(src_path)
    parse_result, awst, compilation_set, awst_logs = get_awst_cache(root_dir)
    awst_logs = _filter_logs(awst_logs, root_dir, src_path)

    awst_errors = _get_log_errors(awst_logs)
    if awst_errors:
        raise CodeError(awst_errors)
    # create a new context from cache and specified src
    with logging_context() as log_ctx:
        narrow_sources_by_path, narrow_compilation_set = narrowed_compile_context(
            parse_result, src_path, awst, compilation_set, options
        )

        with pushd(root_dir):
            if options.output_awst and options.out_dir:
                # this should be correct and exhaustive but relies on independence of examples
                nodes = [n for n in awst if n.source_location.file in narrow_sources_by_path]
                output_awst(nodes, options.out_dir)

            try:
                teal = awst_to_teal(
                    log_ctx, options, narrow_compilation_set, narrow_sources_by_path, awst
                )
            except SystemExit as ex:
                raise CodeError(_get_log_errors(log_ctx.logs)) from ex

            filtered_teal = [t for t in teal if t.id in narrow_compilation_set]

            if options.output_client:
                write_arc4_clients(
                    options.template_vars_prefix, narrow_compilation_set, filtered_teal
                )

        return CompilationResult(
            module_awst=awst,
            logs=awst_logs + log_ctx.logs,
            teal=filtered_teal,
            root_dir=root_dir,
            src_path=src_path,
        )


@attrs.frozen
class PuyaTestCase:
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


def load_template_vars(path: Path | None) -> tuple[str, dict[str, int | bytes]]:
    prefix = "TMPL_"
    prefix_prefix = "prefix="

    result = {}
    if path is not None:
        for line in path.read_text("utf8").splitlines():
            if line.startswith(prefix_prefix):
                prefix = line.removeprefix(prefix_prefix)
            else:
                key, value = parse_template_key_value(line)
                result[key] = value
    return prefix, result
