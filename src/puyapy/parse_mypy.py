import functools
import os
import sys
import typing
from collections.abc import Mapping
from pathlib import Path

from mypy.build import BuildManager, load_graph, order_ascc, process_stale_scc, sorted_components
from mypy.error_formatter import ErrorFormatter
from mypy.errors import SHOW_NOTE_CODES, Errors, MypyError
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.nodes import MypyFile
from mypy.options import Options as MypyOptions
from mypy.plugins.default import DefaultPlugin
from mypy.typestate import reset_global_state, type_state
from mypy.util import read_py_file
from mypy.version import __version__ as mypy_version

from puya import log
from puya.errors import InternalError
from puya.parse import SourceLocation

if typing.TYPE_CHECKING:
    from puyapy.parse import _ModuleData

logger = log.get_logger(__name__)


def mypy_parse(
    module_data: Mapping[str, "_ModuleData"], fs_cache: FileSystemCache
) -> tuple[MypyOptions, Mapping[str, MypyFile]]:
    mypy_build_sources = [
        BuildSource(
            path=str(md.path),  # TODO: figure out why omitting this fails in pytest only
            module=module,
            text=md.data,
            followed=not md.is_source,
        )
        for module, md in module_data.items()
        if md.path.is_file()
    ]
    mypy_options = _get_mypy_options()
    typeshed_paths, algopy_sources = _typeshed_paths()
    mypy_search_paths = SearchPaths(
        python_path=(),
        package_path=(),
        typeshed_path=tuple(map(str, typeshed_paths)),
        mypy_path=(),
    )
    sorted_modules = _mypy_build(
        mypy_build_sources, mypy_options, mypy_search_paths, fs_cache, algopy_sources
    )
    missing_module_names = {bs.module for bs in mypy_build_sources} - sorted_modules.keys()
    # Note: this shouldn't happen, provided we've successfully disabled the mypy cache
    assert (
        not missing_module_names
    ), f"mypy parse failed, missing modules: {', '.join(missing_module_names)}"
    return mypy_options, sorted_modules


_CUSTOM_TYPESHED_PATH = Path(__file__).parent / "_typeshed"


def _get_mypy_options() -> MypyOptions:
    mypy_opts = MypyOptions()

    # improve mypy parsing performance by using a cut-down typeshed
    mypy_opts.custom_typeshed_dir = str(_CUSTOM_TYPESHED_PATH)
    mypy_opts.abs_custom_typeshed_dir = str(_CUSTOM_TYPESHED_PATH.resolve())

    # not required, we compute search paths ourselves
    mypy_opts.python_executable = None
    mypy_opts.preserve_asts = True
    mypy_opts.include_docstrings = True
    # next two options disable caching entirely.
    # slows things down but prevents intermittent failures.
    mypy_opts.incremental = False
    mypy_opts.cache_dir = os.devnull

    # strict mode flags, need to review these and all others too
    mypy_opts.disallow_any_generics = True
    mypy_opts.disallow_subclassing_any = True
    mypy_opts.disallow_untyped_calls = True
    mypy_opts.disallow_untyped_defs = True
    mypy_opts.disallow_incomplete_defs = True
    mypy_opts.check_untyped_defs = True
    mypy_opts.disallow_untyped_decorators = True
    mypy_opts.warn_redundant_casts = True
    mypy_opts.warn_unused_ignores = True
    mypy_opts.warn_return_any = True
    mypy_opts.strict_equality = True
    mypy_opts.strict_concatenate = True

    # disallow use of any
    mypy_opts.disallow_any_unimported = True
    # should be True but: https://github.com/python/mypy/issues/18770
    mypy_opts.disallow_any_expr = False
    mypy_opts.disallow_any_decorated = True
    mypy_opts.disallow_any_explicit = True

    mypy_opts.pretty = True  # show source in output
    mypy_opts.fast_module_lookup = True  # look modules up in source set first

    return mypy_opts


def _mypy_build(
    sources: list[BuildSource],
    options: MypyOptions,
    search_paths: SearchPaths,
    fscache: FileSystemCache,
    algopy_sources: Mapping[str, Path],
) -> dict[str, MypyFile]:
    """Simple wrapper around mypy.build.build

    Makes it so that check errors and parse errors are handled the same (ie with an exception)
    """
    algopy_build_sources = [
        BuildSource(path=str(v), module=k, followed=True) for k, v in algopy_sources.items()
    ]
    source_set = BuildSourceSet(sources + algopy_build_sources)
    cached_read = fscache.read
    errors = Errors(options, read_source=lambda path: read_py_file(path, cached_read))
    plugin = DefaultPlugin(options)
    reporter = _LogReporter()

    def ignore_error(*_args: object) -> None:
        pass

    # Construct a build manager object to hold state during the build.
    #
    # Ignore current directory prefix in error messages.
    manager = BuildManager(
        data_dir=os.devnull,
        search_paths=search_paths,
        ignore_prefix=os.getcwd(),  # noqa: PTH109
        source_set=source_set,
        reports=None,
        options=options,
        version_id=mypy_version,
        plugin=plugin,
        plugins_snapshot={},
        errors=errors,
        error_formatter=reporter,
        flush_errors=ignore_error,
        fscache=fscache,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    reset_global_state()
    graph = load_graph(sources, manager)
    for algopy_module, algopy_module_path in algopy_sources.items():
        graph[algopy_module].ignore_all = True
        manager.errors.ignored_files.add(str(algopy_module_path))
    # process_graph(graph, manager)
    sccs = sorted_components(graph)
    sorted_modules = list[str]()
    # We're processing SCCs from leaves (those without further
    # dependencies) to roots (those from which everything else can be
    # reached).
    for ascc in sccs:
        # Order the SCC's nodes using a heuristic.
        # Note that ascc is a set, and scc is a list.
        scc = order_ascc(graph, ascc)
        # Make the order of the SCC that includes 'builtins' and 'typing',
        # among other things, predictable. Various things may  break if
        # the order changes.
        if "builtins" in ascc:
            scc = sorted(scc, reverse=True)
            # If builtins is in the list, move it last.  (This is a bit of
            # a hack, but it's necessary because the builtins module is
            # part of a small cycle involving at least {builtins, abc,
            # typing}.  Of these, builtins must be processed last or else
            # some builtin objects will be incompletely processed.)
            scc.remove("builtins")
            scc.append("builtins")
        sorted_modules.extend(scc)
        process_stale_scc(graph, scc, manager)

    type_state.reset_all_subtype_caches()
    # Sometimes when we call back into mypy, there might be errors.
    # We don't want to crash when that happens.
    manager.errors.set_file("<puyapy>", module=None, scope=None, options=options)
    return {module_name: manager.modules[module_name] for module_name in sorted_modules}


class _LogReporter(ErrorFormatter):
    """Formatter for basic JSON output format."""

    def report_error(self, error: MypyError) -> str:
        if error.file_path != os.devnull:
            match error.severity:
                case "note":
                    level = log.LogLevel.info
                case level_str:
                    level = log.LogLevel[level_str]
            resolved_path = Path(error.file_path).resolve()
            location = SourceLocation(
                file=resolved_path,
                line=max(error.line, 1),
                column=error.column if error.column >= 0 else None,
            )
            message = error.message
            if error.errorcode and (
                error.severity != "note" or error.errorcode in SHOW_NOTE_CODES
            ):
                # If note has an error code, it is related to a previous error. Avoid
                # displaying duplicate error codes.
                message = f"{message}  [{error.errorcode.code}]"
            logger.log(level, message, location=location)
        return ""


@functools.cache
def _typeshed_paths() -> tuple[tuple[Path, ...], Mapping[str, Path]]:
    """Return default standard library search paths. Guaranteed to be normalised."""
    custom_typeshed_dir = _CUSTOM_TYPESHED_PATH.resolve()
    if not custom_typeshed_dir.is_dir():
        raise InternalError("puyapy install is corrupted - missing typeshed directory")
    typeshed_dir = custom_typeshed_dir / "stdlib"
    if not typeshed_dir.is_dir():
        raise InternalError("puyapy install is corrupted - missing typeshed stlib directory")
    versions_file = typeshed_dir / "VERSIONS"
    if not versions_file.is_file():
        raise InternalError("puyapy install is corrupted - missing typeshed VERSIONS file")
    mypy_extensions_dir = custom_typeshed_dir / "stubs" / "mypy-extensions"
    if not mypy_extensions_dir.is_dir():
        raise InternalError(
            "puyapy install is corrupted - missing typeshed mypy-extensions directory"
        )

    algopy_stubs = typeshed_dir / "algopy"
    # TODO: remove below hack once mypy migration is complete
    if not algopy_stubs.exists():
        logger.info("algopy-stubs not installed in typeshed, assuming puyapy development mode")
        puyapy_dir = Path(__file__).parent
        vcs_root = puyapy_dir.parent.parent
        stubs_dir = vcs_root / "stubs"
        algopy_stubs = stubs_dir / "algopy-stubs"
    if not algopy_stubs.is_dir():
        raise InternalError("puyapy install is corrupted - algopy stubs not a directory")
    algopy_sources = dict[str, Path]()
    for algopy_stub_file in sorted(algopy_stubs.glob("*.pyi")):
        if algopy_stub_file.stem == "__init__":
            module_name = "algopy"
        else:
            module_name = f"algopy.{algopy_stub_file.stem}"
        algopy_sources[module_name] = algopy_stub_file
    return (typeshed_dir, mypy_extensions_dir), algopy_sources
