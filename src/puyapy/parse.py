import codecs
import enum
import functools
import graphlib
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import typing
from collections import deque
from collections.abc import Collection, Mapping, Sequence, Set
from functools import cached_property
from importlib import metadata
from pathlib import Path

import attrs
from mypy.build import BuildManager, dispatch, sorted_components
from mypy.errors import Errors
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.nodes import MypyFile
from mypy.options import Options as MypyOptions
from mypy.plugins.default import DefaultPlugin
from mypy.types import instance_cache
from mypy.typestate import reset_global_state, type_state
from mypy.util import decode_python_encoding, find_python_encoding, hash_digest, read_py_file
from mypy.version import __version__ as mypy_version
from packaging import version

from puya import log
from puya.errors import CodeError, ConfigurationError, InternalError
from puya.parse import SourceLocation
from puya.utils import make_path_relative_to_cwd, set_add
from puyapy import interpreter_data
from puyapy.dependency_analysis import Dependency, DependencyFlags, ImportDependencyResolver
from puyapy.fast.builder import parse_module
from puyapy.fast.nodes import Module as FastModule
from puyapy.find_sources import ResolvedSource, create_source_list

logger = log.get_logger(__name__)

# this should contain the lowest version number that this compiler does NOT support
# i.e. the next minor version after what is defined in stubs/pyproject.toml:project.version
MAX_SUPPORTED_ALGOPY_VERSION_EX = version.parse("3.5.0")
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

    sources_by_module_name, package_roots = _create_and_check_source_list(
        paths, excluded_subdir_names=excluded_subdir_names
    )
    sources_by_module_name = dict(sorted(sources_by_module_name.items()))

    package_paths = _resolve_package_paths(package_search_paths)
    fs_cache = FileSystemCache()
    # prime the cache with supplied content overrides, so that mypy reads from our data instead
    if file_contents:
        for content_path, content in file_contents.items():
            fn = str(content_path)
            data = content.encode("utf-8")
            fs_cache.stat_or_none(fn)
            fs_cache.read_cache[fn] = data
            fs_cache.hash_cache[fn] = hash_digest(data)

    module_data = _find_dependencies(
        sources_by_module_name.values(),
        fs_cache,
        package_roots=package_roots,
        package_paths=package_paths,
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
    base_dir_by_pkg = dict[str, Path | None]()
    package_roots = dict[str, Path]()
    errors = list[ConfigurationError]()
    for bs in build_sources:
        existing = sources_by_module_name.setdefault(bs.module, bs)
        if existing != bs:
            errors.append(
                ConfigurationError(
                    f"duplicate modules named in build sources:"
                    f" {make_path_relative_to_cwd(bs.path)} has same module name '{bs.module}'"
                    f" as {make_path_relative_to_cwd(existing.path)}"
                )
            )
        else:
            existing = sources_by_path.setdefault(bs.path, bs)
            if existing != bs:
                errors.append(
                    ConfigurationError(
                        f"source path {make_path_relative_to_cwd(bs.path)}"
                        f" was resolved to multiple module names, ensure each path is only"
                        f" specified once or add top-level __init__.py files to mark package roots"
                    )
                )
            else:
                pkg = bs.module.partition(".")[0]
                # TODO: use just package_roots instead of also having base_dir_by_pkg
                existing_base = base_dir_by_pkg.setdefault(pkg, bs.base_dir)
                if existing_base == bs.base_dir:
                    if bs.base_dir is None:
                        assert bs.path.suffix == ".py" and not bs.path.name.startswith("__init__.")
                        package_roots[pkg] = bs.path
                    else:
                        init_path = bs.base_dir / pkg / "__init__.py"
                        assert init_path.is_file()
                        package_roots[pkg] = init_path
                else:
                    if existing_base is None:
                        conflict_msg = (
                            f"module '{bs.module}' appears to be a package"
                            f" rooted at {bs.base_dir},"
                            f" which conflicts with a standalone module '{pkg}'"
                        )
                    elif bs.base_dir is None:
                        conflict_msg = (
                            f"module '{bs.module}' appears to be a standalone module,"
                            f" which conflicts with a package of the same name"
                            f" rooted at {existing_base}"
                        )
                    else:
                        conflict_msg = (
                            f"module '{bs.module}' appears to be a package"
                            f" rooted at {bs.base_dir},"
                            f" which conflicts with existing package root {existing_base}"
                        )
                    errors.append(ConfigurationError(conflict_msg))
    if errors:
        raise ExceptionGroup("source conflicts", errors)
    return sources_by_module_name, package_roots


def _resolve_package_paths(
    package_search_paths: Sequence[str] | typing.Literal["infer", "current"],
) -> list[Path]:
    match package_search_paths:
        case "current":
            sys_path = interpreter_data.get_sys_path()
        case "infer":
            sys_path = _infer_sys_path()
        case paths:
            sys_path = [os.path.abspath(p) for p in paths]  # noqa: PTH100
    logger.info(f"using python search path: {sys_path}")
    _check_algopy_version(sys_path)
    return [Path(p) for p in sys_path]


def _infer_sys_path() -> list[str]:
    # 1) Look for VIRTUAL_ENV as we want the venv puyapy is being run against (i.e. the project).
    # 2) If no venv is active, then fallback to the python interpreter on the system path.
    # 3) Failing that, use the current interpreter.
    # In the future, we might want to make it 1 -> 3 -> error, since searching the system path
    # for a python executable is just as likely to be incorrect as using the currently running one,
    # with extra downside that it's less predictable.
    # To continue to support the current method, we could add a --python-executable=... CLI option.
    try:
        venv = os.environ["VIRTUAL_ENV"]
    except KeyError:
        logger.debug("no active python virtual env")
        venv_scripts = None
    else:
        logger.debug(f"found active python virtual env: {venv}")
        venv_paths = sysconfig.get_paths(vars={"base": venv})
        venv_scripts = venv_paths["scripts"]
    for python in ("python3", "python"):
        logger.debug(f"attempting to locate '{python}' in {venv_scripts or 'system path'}")
        python_exe = shutil.which(python, path=venv_scripts)
        if python_exe:
            logger.debug(f"using python search path from interpreter: {python_exe}")
            return get_sys_path(python_exe)
    if venv_scripts:
        raise ConfigurationError(
            "found an active python virtual env, but could not find an expected python interpreter"
        )
    logger.debug("using python search path from current interpreter")
    return interpreter_data.get_sys_path()


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


def _find_dependencies(
    sources: Collection[ResolvedSource],
    fs_cache: FileSystemCache,
    *,
    package_roots: Mapping[str, Path],
    package_paths: Sequence[Path],
) -> dict[str, _ModuleData]:
    resolver = ImportDependencyResolver(package_roots=package_roots, package_paths=package_paths)
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
            dependencies = resolver.resolve_import_dependencies(rs, fast)
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
        module_name: manager.modules[module_name]
        for scc in sccs
        for module_name in sorted(scc.mod_ids)
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


def get_sys_path(python_executable: str) -> list[str]:
    # Use subprocess to get the package directory of given Python
    # executable
    env = os.environ.copy() | {"PYTHONSAFEPATH": "1"}
    try:
        pyinfo_result = subprocess.run(  # noqa: S603
            [python_executable, interpreter_data.__file__],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as err:
        assert err.errno is not None
        reason = os.strerror(err.errno)
        raise ConfigurationError(
            f"invalid python executable '{python_executable}': {reason}"
        ) from err
    if pyinfo_result.returncode != 0:
        if pyinfo_result.stderr:
            raise ConfigurationError(pyinfo_result.stderr)
        raise InternalError(f"failed to inspect python environment for {python_executable}")
    sys_path = pyinfo_result.stdout.splitlines()
    return sys_path


_STUBS_PACKAGE_NAME = "algorand-python"


def _check_algopy_version(site_packages: list[str]) -> None:
    pkgs = metadata.Distribution.discover(name=_STUBS_PACKAGE_NAME, path=site_packages)
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
