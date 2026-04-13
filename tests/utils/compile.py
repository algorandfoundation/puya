import contextlib
import functools
import inspect
import json
import tempfile
import textwrap
import typing
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import Path

import algokit_utils as au
import attrs

from puya.arc56 import create_arc56_json
from puya.awst import nodes as awst_nodes
from puya.awst.serialize import awst_from_json
from puya.compilation_artifacts import CompilationArtifact, CompiledContract
from puya.compile import awst_to_teal
from puya.errors import CodeError, PuyaExitError
from puya.log import Log, LogLevel, logging_context
from puya.options import PuyaOptions
from puya.parse import SourceLocation
from puya.program_refs import ContractReference, LogicSigReference
from puya.utils import coalesce, pushd, read_text_from_maybe_compressed_file
from puyapy.awst_build.main import transform_ast
from puyapy.compile import determine_out_dir, output_awst, write_arc4_clients
from puyapy.options import PuyaPyOptions
from puyapy.parse import ParseResult, SourceDiscoveryMechanism, parse_python
from tests import VCS_ROOT
from tests.utils import OPT_SUFFIXES, PuyaPyOptionsKwargs, PuyaTestCase, load_template_vars

UNSTABLE_LOG_PREFIXES = {
    LogLevel.debug: (
        "Building AWST for ",
        "Skipping algopy stub ",
        "Skipping typeshed stub ",
        "Skipping stdlib stub ",
        "Discovered user module ",
        # ignore platform specific paths
        "found algopy: ",
        "found active python virtual env: ",
        "no active python virtual env",
        "attempting to locate 'python",
        "using python search path from ",
    ),
    LogLevel.info: (
        # ignore platform specific paths
        "using python search path: ",
    ),
}


class _CompileCache(typing.NamedTuple):
    parse_result: ParseResult
    module_awst: awst_nodes.AWST
    compilation_set: Sequence[ContractReference | LogicSigReference]
    logs: Sequence[Log]


@functools.cache
def get_awst_cache(root_dir: Path) -> _CompileCache:
    # note that this caching assumes that AWST is the same across all
    # optimisation and debug levels, which is currently true.
    # if this were to no longer be true, this test speedup strategy would need to be revisited
    with pushd(root_dir), logging_context() as log_ctx:
        # explicitly exclude out dirs as they can contain generated clients that get deleted
        out_dir_names = [f"out{suffix}" for suffix in OPT_SUFFIXES.values()]
        parse_result = parse_python([root_dir], excluded_subdir_names=out_dir_names)
        awst, compilation_set = transform_ast(parse_result, PuyaPyOptions())
    return _CompileCache(parse_result, awst, compilation_set, log_ctx.logs)


@attrs.frozen(kw_only=True)
class CompilationResult:
    options: PuyaOptions
    logs: list[Log]
    teal: list[CompilationArtifact]


def narrowed_compile_context(
    parse_result: ParseResult,
    src_path: Path,
    awst: awst_nodes.AWST,
    compilation_set: Collection[ContractReference | LogicSigReference],
    puyapy_options: PuyaPyOptions,
) -> tuple[
    Mapping[Path, Sequence[str] | None],
    Mapping[ContractReference | LogicSigReference, Path],
]:
    narrowed_sources_by_path = {
        sm.path: sm.lines
        for sm in parse_result.ordered_modules.values()
        if sm.path.resolve().is_relative_to(src_path)
        and sm.discovery_mechanism != SourceDiscoveryMechanism.dependency
    }
    awst_lookup = {n.id: n for n in awst}
    compilation_set = {
        target_id: determine_out_dir(loc.file.parent, puyapy_options)
        for target_id, loc in ((t, awst_lookup[t].source_location) for t in compilation_set)
        if loc.file in narrowed_sources_by_path
    }
    return narrowed_sources_by_path, compilation_set


def _filter_logs(logs: Sequence[Log], root_dir: Path, src_path: Path) -> list[Log]:
    root_dir = root_dir.resolve()
    relative_src_root = src_path.relative_to(root_dir)
    result = []
    for log_ in logs:
        # ignore logs that come from files outside of src_path as these are
        # logs emitted during the cached AWST parsing step
        relative_path = get_relative_path(log_.location, root_dir)
        if relative_path and relative_src_root not in (
            relative_path,
            *relative_path.parents,
        ):
            continue

        # ignore logs that are not output in a consistent order
        log_prefixes_to_ignore = UNSTABLE_LOG_PREFIXES.get(log_.level)
        if log_prefixes_to_ignore and log_.message.startswith(log_prefixes_to_ignore):
            continue

        result.append(log_)
    return result


def get_relative_path(location: SourceLocation | None, root_dir: Path) -> Path | None:
    if not location or not location.file:
        return None
    path = location.file
    with contextlib.suppress(ValueError):
        path = path.relative_to(root_dir)
    return path


def _group_and_raise_log_errors(logs: Iterable[Log]) -> None:
    errors = [CodeError(log.message, log.location) for log in logs if log.level >= LogLevel.error]
    if errors:
        raise ExceptionGroup("compilation failed", errors)


def compile_from_test_case(
    test_case: PuyaTestCase,
    out_dir: Path | None = None,
    **puyapy_options: typing.Unpack[PuyaPyOptionsKwargs],
) -> CompilationResult:
    out_dir = coalesce(out_dir, Path("out_tests"))
    prefix, template_vars = load_template_vars(test_case.template_vars_path)
    puyapy_options.setdefault("template_vars_prefix", prefix)
    puyapy_options.setdefault("cli_template_definitions", template_vars)
    options = PuyaPyOptions(paths=[test_case.test_case], out_dir=out_dir, **puyapy_options)
    if test_case.is_awst:
        # suppress front end only outputs
        options = attrs.evolve(options, output_awst=False, output_client=False)
        awst = load_test_case_awst(test_case.path)
        compilation_out_dir = determine_out_dir(test_case.test_case, options)
        compilation_set = get_compilation_set(awst, compilation_out_dir)

        return _compile_from_awst(
            test_case,
            awst,
            compilation_set,
            options,
            sources_by_path={},
        )
    else:
        return _compile_from_python(test_case, options)


def load_test_case_json(path: Path) -> str:
    awst_path = path / "module.awst.json"
    if not awst_path.exists():
        awst_path = awst_path.with_suffix(".json.gz")
    awst_json = read_text_from_maybe_compressed_file(awst_path)
    return awst_json.replace("%DIR%", str(path).replace("\\", "\\\\"))


def load_test_case_awst(path: Path) -> awst_nodes.AWST:
    awst_json = load_test_case_json(path)
    return awst_from_json(awst_json)


def get_compilation_set(
    awst: awst_nodes.AWST, out_dir: Path
) -> dict[ContractReference | LogicSigReference, Path]:
    return {
        node.id: out_dir
        for node in awst
        if isinstance(node, awst_nodes.Contract | awst_nodes.LogicSignature)
    }


def _compile_from_python(test_case: PuyaTestCase, options: PuyaPyOptions) -> CompilationResult:
    src_path = test_case.path.resolve()
    root_dir = test_case.root
    parse_result, awst, compilation_set, awst_logs = get_awst_cache(root_dir)
    awst_logs = _filter_logs(awst_logs, root_dir, src_path)

    _group_and_raise_log_errors(awst_logs)
    # create a new context from cache and specified src
    narrow_sources_by_path, narrow_compilation_set = narrowed_compile_context(
        parse_result, src_path, awst, compilation_set, options
    )
    # this should be correct and exhaustive but relies on independence of examples
    narrowed_awst = [n for n in awst if n.source_location.file in narrow_sources_by_path]
    result = _compile_from_awst(
        test_case,
        narrowed_awst,
        narrow_compilation_set,
        options,
        sources_by_path=narrow_sources_by_path,
    )
    # normalise path for log output
    options = attrs.evolve(options, paths=(Path(src_path.name),))
    return attrs.evolve(
        result,
        logs=[
            Log(level=LogLevel.debug, message=repr(options), location=None),
            *awst_logs,
            *result.logs,
        ],
    )


def _compile_from_awst(
    test_case: PuyaTestCase,
    awst: awst_nodes.AWST,
    compilation_set: Mapping[ContractReference | LogicSigReference, Path],
    options: PuyaPyOptions,
    *,
    sources_by_path: Mapping[Path, Sequence[str] | None],
) -> CompilationResult:
    with logging_context() as log_ctx, pushd(test_case.root):
        if options.output_awst and options.out_dir:
            output_awst(awst, options.out_dir)

        try:
            teal = awst_to_teal(log_ctx, options, compilation_set, sources_by_path, awst)
        except PuyaExitError:
            _group_and_raise_log_errors(log_ctx.logs)
            raise  # above should raise, but it doesn't fall back to original exception

        if options.output_client:
            write_arc4_clients(options.template_vars_prefix, compilation_set, teal)

        return CompilationResult(
            options=options,
            logs=list(log_ctx.logs),
            teal=teal,
        )


def compile_arc56(
    test_case_or_path: Path | PuyaTestCase,
    *,
    optimization_level: int = 1,
    debug_level: int = 2,
    contract_name: str | None = None,
    disabled_optimizations: Sequence[str] = (),
    validate_abi_args: bool = True,
) -> au.Arc56Contract:
    if isinstance(test_case_or_path, Path):
        test_case = PuyaTestCase(test_case_or_path)
    else:
        test_case = test_case_or_path

    result = compile_from_test_case(
        test_case,
        optimization_level=optimization_level,
        debug_level=debug_level,
        optimizations_override={o: False for o in disabled_optimizations},
        validate_abi_args=validate_abi_args,
    )
    if contract_name is None:
        (contract,) = result.teal
    else:
        (contract,) = (
            t
            for t in result.teal
            if isinstance(t, CompiledContract)
            if t.metadata.name == contract_name
        )

    assert isinstance(contract, CompiledContract), "Compilation artifact must be a contract"
    return arc56_from_compiled_contract(contract)


def arc56_from_compiled_contract(contract: CompiledContract) -> au.Arc56Contract:
    arc56_json = create_arc56_json(
        metadata=contract.metadata,
        approval_program=contract.approval_program,
        clear_program=contract.clear_program,
        template_prefix="TMPL_",
    )
    return au.Arc56Contract.from_json(arc56_json)


def compile_arc56_from_closure(
    closure: typing.Callable[[], None], *, optimization_level: int = 1
) -> au.Arc56Contract:
    with tempfile.TemporaryDirectory() as root_dir_:
        root_dir = Path(root_dir_)
        test_case = root_dir / "test"
        test_case.mkdir(exist_ok=True)
        src_path = test_case / "contract.py"
        source = inspect.getsource(closure)
        closure_lines = source.splitlines()[1:]
        closure_text_block = textwrap.dedent("\n".join(closure_lines))
        src_path.write_text(closure_text_block, encoding="utf-8")
        return compile_arc56(test_case, optimization_level=optimization_level)


def log_to_str(log: Log, root_dir: Path) -> str:
    if log.location and log.location.file:
        relative_path = get_relative_path(log.location, root_dir)
        col = f":{log.location.column + 1}" if log.location.column else ""
        location = f"{relative_path!s}:{log.location.line}{col} "
    else:
        location = ""
    return normalize_log(f"{location}{log.level}: {log.message}")


def _normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


_NORMALIZED_VCS = _normalize_path(VCS_ROOT)


def normalize_log(log: str) -> str:
    return log.replace("\\", "/").replace(_NORMALIZED_VCS, "<git root>")


def normalize_arc56(directory: Path) -> None:
    for arc56_file in directory.rglob("*.arc56.json"):
        arc56 = json.loads(arc56_file.read_text(encoding="utf8"))
        compiler_version = arc56.get("compilerInfo", {}).get("compilerVersion", {})
        compiler_version["major"] = 99
        compiler_version["minor"] = 99
        compiler_version["patch"] = 99
        arc56_file.write_text(json.dumps(arc56, indent=4), encoding="utf8")
