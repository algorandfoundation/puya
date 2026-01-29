import functools
import os
import re
import sys
import typing
from collections.abc import Mapping
from pathlib import Path

from mypy.build import (
    BuildManager,
    State as MypyState,
    dispatch,
    order_ascc,
    sorted_components,
)
from mypy.errors import Errors
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.options import Options as MypyOptions
from mypy.plugins.default import DefaultPlugin
from mypy.types import instance_cache
from mypy.typestate import reset_global_state, type_state
from mypy.util import hash_digest, read_py_file
from mypy.version import __version__ as mypy_version

from puya import log
from puya.errors import InternalError
from puya.parse import SourceLocation

if typing.TYPE_CHECKING:
    from puyapy.parse import _ModuleData

logger = log.get_logger(__name__)


def mypy_parse(
    module_data: Mapping[str, "_ModuleData"],
) -> tuple[MypyOptions, Mapping[str, MypyState]]:
    fs_cache = FileSystemCache()
    # prime the cache with supplied content overrides, so that mypy reads from our data instead
    for md in module_data.values():
        fn = str(md.path)
        data = md.text.encode("utf-8")
        fs_cache.stat_or_none(fn)
        fs_cache.read_cache[fn] = data
        fs_cache.hash_cache[fn] = hash_digest(data)

    mypy_build_sources = [
        BuildSource(
            path=str(md.path),  # TODO: figure out why omitting this fails in pytest only
            module=module,
            text=md.text,
            followed=not md.is_source,
        )
        for module, md in module_data.items()
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
) -> dict[str, MypyState]:
    """
    Our own implementation of mypy.build.build which handles errors via logging,
    and uses our computed search paths.
    """
    all_messages = list[str]()

    instance_cache.reset()

    def flush_errors(
        _filename: str | None,
        new_messages: list[str],
        _is_serious: bool,  # noqa: FBT001
    ) -> None:
        all_messages.extend(msg for msg in new_messages if os.devnull not in msg)

    algopy_build_sources = [
        BuildSource(path=str(v), module=k, followed=True) for k, v in algopy_sources.items()
    ]
    source_set = BuildSourceSet(sources + algopy_build_sources)
    cached_read = fscache.read
    errors = Errors(options, read_source=lambda path: read_py_file(path, cached_read))
    plugin = DefaultPlugin(options)

    # Construct a build manager object to hold state during the build.
    manager = BuildManager(
        data_dir=os.devnull,
        search_paths=search_paths,
        # Ignore current directory prefix in error messages.
        ignore_prefix=os.getcwd(),  # noqa: PTH109
        source_set=source_set,
        reports=None,
        options=options,
        version_id=mypy_version,
        plugin=plugin,
        plugins_snapshot={},
        errors=errors,
        flush_errors=flush_errors,
        fscache=fscache,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    reset_global_state()
    graph = dispatch(sources, manager, sys.stdout)
    _log_mypy_messages(all_messages)
    if not options.fine_grained_incremental:
        type_state.reset_all_subtype_caches()
    # Sometimes when we call back into mypy, there might be errors.
    # We don't want to crash when that happens.
    manager.errors.set_file("<puyapy>", module=None, scope=None, options=options)
    sccs = sorted_components(graph)
    return {
        module_name: graph[module_name]
        for scc in sccs
        for module_name in order_ascc(graph, scc.mod_ids)
    }


def _log_mypy_message(message: log.Log | None, related_lines: list[str]) -> None:
    if not message:
        return
    logger.log(
        message.level, message.message, location=message.location, related_lines=related_lines
    )


def _log_mypy_messages(messages: list[str]) -> None:
    first_message: log.Log | None = None
    related_messages = list[str]()
    for message_str in messages:
        message = _parse_log_message(message_str)
        if not first_message:
            first_message = message
        elif not message.location:
            # collate related error messages and log together
            related_messages.append(message.message)
        else:
            _log_mypy_message(first_message, related_messages)
            related_messages = []
            first_message = message
    _log_mypy_message(first_message, related_messages)


_MYPY_LOG_MESSAGE = re.compile(
    r"""^
    (?P<filename>([A-Z]:\\)?[^:]*)(:(?P<line>\d+))?
    :\s(?P<severity>error|warning|note)
    :\s(?P<msg>.*)$""",
    re.VERBOSE,
)


def _parse_log_message(log_message: str) -> log.Log:
    match = _MYPY_LOG_MESSAGE.match(log_message)
    if match:
        matches = match.groupdict()
        return _try_parse_log_parts(
            matches.get("filename"),
            matches.get("line") or "",
            matches.get("severity") or "error",
            matches["msg"],
        )
    return log.Log(
        level=log.LogLevel.error,
        message=log_message,
        location=None,
    )


_MYPY_SEVERITY_TO_LOG_LEVEL: typing.Final = {
    "error": log.LogLevel.error,
    "warning": log.LogLevel.warning,
    "note": log.LogLevel.info,
}


def _try_parse_log_parts(
    path_str: str | None, line_str: str, severity_str: str, msg: str
) -> log.Log:
    if not path_str:
        location = None
    else:
        try:
            line = int(line_str)
        except ValueError:
            line = 1
        location = SourceLocation(file=Path(path_str).resolve(), line=line)
    level = _MYPY_SEVERITY_TO_LOG_LEVEL[severity_str]
    return log.Log(message=msg, level=level, location=location)


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
