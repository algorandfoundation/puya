import codecs
import enum
import functools
import graphlib
import os
import sys
import typing
from collections import deque
from collections.abc import Collection, Mapping, Sequence, Set
from functools import cached_property
from importlib import metadata
from pathlib import Path

import attrs
from mypy.build import (
    BuildManager,
    load_graph,
    order_ascc,
    process_stale_scc,
    sorted_components,
)
from mypy.error_formatter import ErrorFormatter
from mypy.errors import SHOW_NOTE_CODES, Errors, MypyError
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.nodes import MypyFile
from mypy.options import Options as MypyOptions
from mypy.plugins.default import DefaultPlugin
from mypy.typestate import reset_global_state, type_state
from mypy.util import decode_python_encoding, find_python_encoding, hash_digest, read_py_file
from mypy.version import __version__ as mypy_version
from packaging import version

from puya import log
from puya.errors import CodeError, ConfigurationError, InternalError
from puya.parse import SourceLocation
from puya.utils import make_path_relative_to_cwd, set_add
from puyapy.dependency_analysis import (
    Dependency,
    DependencyFlags,
    resolve_import_dependencies,
)
from puyapy.fast.builder import parse_module
from puyapy.fast.nodes import Module as FastModule
from puyapy.find_sources import ResolvedSource, create_source_list
from puyapy.package_path import PackageResolverCache, resolve_package_paths

logger = log.get_logger(__name__)

# this should contain the lowest version number that this compiler does NOT support
# i.e. the next minor version after what is defined in stubs/pyproject.toml:project.version
MAX_SUPPORTED_ALGOPY_VERSION_EX = version.parse("3.4.0")
MIN_SUPPORTED_ALGOPY_VERSION = version.parse(f"{MAX_SUPPORTED_ALGOPY_VERSION_EX.major}.0.0")


class SourceDiscoveryMechanism(enum.Enum):
    explicit = enum.auto()
    dependency = enum.auto()


@attrs.frozen
class SourceModule:
    name: str
    mypy_module: MypyFile
    path: Path
    fast: FastModule | None  # TODO: make this non-optional and handle failures differently
    lines: Sequence[str] | None
    discovery_mechanism: SourceDiscoveryMechanism
    dependencies: frozenset[str]


@attrs.frozen
class ParseResult:
    mypy_options: MypyOptions
    ordered_modules: Mapping[str, SourceModule]
    """All discovered modules, topologically sorted by dependencies.
    The sort order is from leaves (nodes without dependencies) to
    roots (nodes on which no other nodes depend)."""

    @cached_property
    def sources_by_path(self) -> Mapping[Path, Sequence[str] | None]:
        return {s.path: s.lines for s in self.ordered_modules.values()}

    @cached_property
    def explicit_source_paths(self) -> Set[Path]:
        return {
            sm.path
            for sm in self.ordered_modules.values()
            if sm.discovery_mechanism == SourceDiscoveryMechanism.explicit
        }


def parse_python(
    paths: Sequence[Path],
    *,
    package_search_paths: Sequence[str] | typing.Literal["infer", "current"] = "current",
    file_contents: Mapping[Path, str] | None = None,
    excluded_subdir_names: Sequence[str] | None = None,
) -> ParseResult:
    """Generate the ASTs from the build sources, and all imported modules (recursively)"""

    sources_by_module_name, source_roots = _create_and_check_source_list(
        paths, excluded_subdir_names=excluded_subdir_names
    )
    sources_by_module_name = dict(sorted(sources_by_module_name.items()))

    fs_cache = FileSystemCache()
    # prime the cache with supplied content overrides, so that mypy reads from our data instead
    if file_contents:
        for content_path, content in file_contents.items():
            fn = str(content_path)
            data = content.encode("utf-8")
            fs_cache.stat_or_none(fn)
            fs_cache.read_cache[fn] = data
            fs_cache.hash_cache[fn] = hash_digest(data)

    package_paths = resolve_package_paths(package_search_paths)
    _check_algopy_version(package_paths)
    package_cache = PackageResolverCache(package_paths)
    module_data = _fast_parse_and_resolve_imports(
        sources_by_module_name.values(),
        fs_cache,
        source_roots=source_roots,
        package_cache=package_cache,
    )
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

    missing_module_names = sources_by_module_name.keys() - sorted_modules.keys()
    # Note: this shouldn't happen, provided we've successfully disabled the mypy cache
    assert (
        not missing_module_names
    ), f"mypy parse failed, missing modules: {', '.join(missing_module_names)}"

    # order modules by dependency, and also sanity check the contents
    ordered_modules = {}
    module_graph = {
        md.module: sorted(
            {
                dep.module_id
                for dep in md.dependencies
                if not (
                    dep.flags
                    & (
                        DependencyFlags.IMPLICIT
                        | DependencyFlags.TYPE_CHECKING
                        | DependencyFlags.DEFERRED
                        | DependencyFlags.POTENTIAL_STAR_IMPORT
                        | DependencyFlags.STUB
                    )
                )
                and (dep.path and dep.path.is_file())
            }
        )
        for md in module_data.values()
        if md.path.is_file()
    }
    try:
        module_order = list(graphlib.TopologicalSorter(module_graph).static_order())
    except graphlib.CycleError as ex:
        module_cycle: Sequence[str] = ex.args[1]
        raise CodeError(f"cyclical module reference: {' -> '.join(module_cycle)}") from None
    for module_name in module_order:
        mypy_module = sorted_modules[module_name]
        assert (
            module_name == mypy_module.fullname
        ), f"mypy module mismatch, expected {module_name}, got {mypy_module.fullname}"
        md = module_data.pop(module_name)
        assert mypy_module.fullname == md.module, "mypy and fast module name mismatch"
        lines = md.data.splitlines()
        if md.is_source:
            discovery_mechanism = SourceDiscoveryMechanism.explicit
        else:
            discovery_mechanism = SourceDiscoveryMechanism.dependency
        ordered_modules[md.module] = SourceModule(
            name=md.module,
            mypy_module=mypy_module,
            path=md.path,
            lines=lines,
            fast=md.fast,
            discovery_mechanism=discovery_mechanism,
            dependencies=frozenset(dep.module_id for dep in md.dependencies),
        )
    if module_data:
        raise InternalError(f"parse has leftover modules: {', '.join(module_data.keys())}")

    return ParseResult(mypy_options=mypy_options, ordered_modules=ordered_modules)


def _create_and_check_source_list(
    paths: Sequence[Path],
    *,
    excluded_subdir_names: Sequence[str] | None,
) -> tuple[Mapping[str, ResolvedSource], Mapping[str, Path]]:
    build_sources = create_source_list(paths=paths, excluded_subdir_names=excluded_subdir_names)
    sources_by_module_name = dict[str, ResolvedSource]()
    sources_by_path = dict[Path, ResolvedSource]()
    package_roots = dict[str, Path]()
    errors = list[str]()
    seen_pkg_conflicts = set[frozenset[Path]]()
    for bs in build_sources:
        existing = sources_by_module_name.setdefault(bs.module, bs)
        if existing != bs:
            errors.append(
                f"duplicate modules named in build sources:"
                f" {make_path_relative_to_cwd(bs.path)} has same module name '{bs.module}'"
                f" as {make_path_relative_to_cwd(existing.path)}"
            )
            continue
        existing = sources_by_path.setdefault(bs.path, bs)
        if existing != bs:
            errors.append(
                f"source path {make_path_relative_to_cwd(bs.path)}"
                f" was resolved to multiple module names, ensure each path is only"
                f" specified once or add top-level __init__.py files to mark package roots"
            )
            continue
        pkg = bs.module.partition(".")[0]
        if bs.base_dir is None:
            pkg_root = bs.path
            assert pkg_root.suffixes == [".py"] and pkg_root.stem != "__init__"
        else:
            pkg_root = bs.base_dir / pkg / "__init__.py"
            assert pkg_root.is_file()
        existing_root = package_roots.setdefault(pkg, pkg_root)
        if existing_root != pkg_root:
            if not set_add(seen_pkg_conflicts, frozenset((existing_root, pkg_root))):
                continue
            conflict_msg = f"module '{bs.module}' appears to be a"
            if bs.base_dir is None:
                conflict_msg += f" standalone module at {make_path_relative_to_cwd(pkg_root)}"
            else:
                conflict_msg += f" package rooted at {make_path_relative_to_cwd(bs.base_dir)}"
            conflict_msg += ", which conflicts with a"
            existing_is_standalone = existing_root.name != "__init__.py"
            if existing_is_standalone:
                conflict_msg += (
                    f" standalone module of the same name"
                    f" located at {make_path_relative_to_cwd(existing_root)}"
                )
            else:
                conflict_msg += (
                    f" package of the same name"
                    f" rooted at {make_path_relative_to_cwd(existing_root.parent)}"
                )
            errors.append(conflict_msg)
    if errors:
        raise ExceptionGroup("source conflicts", [ConfigurationError(msg) for msg in errors])
    return sources_by_module_name, package_roots


@attrs.frozen
class _ModuleData:
    path: Path
    """File where it's found (e.g. '/home/user/pkg/module.py')"""
    module: str
    """Module name (e.g. 'pkg.module')"""
    data: str
    dependencies: tuple[Dependency, ...]
    """Dependency set, and whether it's a module-level dependency (vs function scoped)"""
    fast: FastModule | None
    is_source: bool


def _fast_parse_and_resolve_imports(
    sources: Collection[ResolvedSource],
    fs_cache: FileSystemCache,
    *,
    source_roots: Mapping[str, Path],
    package_cache: PackageResolverCache,
) -> dict[str, _ModuleData]:
    result_by_id = dict[str, _ModuleData]()
    source_queue = deque(sources)
    queued_id_set = {rs.module for rs in source_queue}
    initial_source_ids = {rs.module for rs in sources}
    while source_queue:
        rs = source_queue.popleft()
        assert rs.module not in result_by_id
        file_bytes = fs_cache.read(str(rs.path))
        _check_encoding(file_bytes, rs.path)
        source = decode_python_encoding(file_bytes)
        fast = parse_module(
            source=source,
            module_path=rs.path,
            module_name=rs.module,
            feature_version=sys.version_info[:2],  # TODO: get this from target interpreter
        )
        if fast is None:
            dependencies = []
        else:
            dependencies = resolve_import_dependencies(
                fast,
                source_roots=source_roots,
                package_cache=package_cache,
                import_base_dir=rs.base_dir or rs.path.parent,
            )
            for dep in dependencies:
                mod_path = dep.path
                if mod_path is None:
                    assert DependencyFlags.STUB in dep.flags
                elif mod_path.is_file() and set_add(queued_id_set, dep.module_id):
                    dep_rs = ResolvedSource(
                        path=mod_path,
                        module=dep.module_id,
                        base_dir=_infer_base_dir(mod_path, dep.module_id),
                    )
                    source_queue.append(dep_rs)
        result_by_id[rs.module] = _ModuleData(
            path=rs.path,
            module=rs.module,
            data=source,
            fast=fast,
            dependencies=tuple(d for d in dependencies if d.module_id != rs.module),
            is_source=rs.module in initial_source_ids,
        )
    return result_by_id


def _infer_base_dir(path: Path, module: str) -> Path:
    # /a/pkg/foo.py, pkg.foo -> /a/
    # /a/pkg/foo/__init__.py, pkg.foo -> /a/
    # /a/foo.py, foo -> /a/
    parts = module.count(".")
    if path.stem == "__init__" and path.suffix in (".py", ".pyi"):
        parts += 1
    return path.parents[parts]


def _check_encoding(source: bytes, module_path: Path) -> None:
    module_rel_path = make_path_relative_to_cwd(module_path)
    module_loc = SourceLocation(file=module_path, line=1)
    # below is based on mypy/util.py:decode_python_encoding
    # check for BOM UTF-8 encoding
    if source.startswith(b"\xef\xbb\xbf"):
        return
    # otherwise look at first two lines and check if PEP-263 coding is present
    encoding, _ = find_python_encoding(source)
    # find the codec for this encoding and check it is utf-8
    codec = codecs.lookup(encoding)
    if codec.name != "utf-8":
        logger.warning(
            "UH OH SPAGHETTI-O's,"
            " darn tootin' non-utf8(?!) encoded file encountered:"
            f" {module_rel_path} encoded as {encoding}",
            location=module_loc,
        )


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


_STUBS_PACKAGE_NAME = "algorand-python"


def _check_algopy_version(site_packages: list[Path]) -> None:
    pkgs = metadata.Distribution.discover(
        name=_STUBS_PACKAGE_NAME, path=[str(p) for p in site_packages]
    )
    try:
        (algopy,) = pkgs
    except ValueError:
        logger.warning("could not determine algopy version")
        return
    algopy_version = version.parse(algopy.version)
    logger.debug(f"found algopy: {algopy_version}")

    if not (MIN_SUPPORTED_ALGOPY_VERSION <= algopy_version < MAX_SUPPORTED_ALGOPY_VERSION_EX):
        logger.warning(
            f"{_STUBS_PACKAGE_NAME} version {algopy_version} is outside the supported range:"
            f" >={MIN_SUPPORTED_ALGOPY_VERSION}, <{MAX_SUPPORTED_ALGOPY_VERSION_EX}",
            important=True,
            related_lines=[
                "This will cause typing errors if there are incompatibilities in the API used.",
                "Please update your algorand-python package to be in the supported range.",
            ],
        )
