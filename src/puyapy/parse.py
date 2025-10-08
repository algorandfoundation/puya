import codecs
import enum
import functools
import os
import shutil
import subprocess
import sys
import sysconfig
import typing
from collections.abc import Mapping, Sequence, Set
from functools import cached_property
from importlib import metadata
from operator import itemgetter
from pathlib import Path

import attrs
from mypy.build import BuildManager, Graph, load_graph, process_graph, sorted_components
from mypy.error_formatter import ErrorFormatter
from mypy.errors import SHOW_NOTE_CODES, Errors, MypyError
from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.nodes import MypyFile
from mypy.options import Options as MypyOptions
from mypy.plugins.default import DefaultPlugin
from mypy.typestate import reset_global_state, type_state
from mypy.util import find_python_encoding, hash_digest, read_py_file
from mypy.version import __version__ as mypy_version
from packaging import version

from puya import log
from puya.errors import ConfigurationError, InternalError
from puya.parse import SourceLocation
from puya.utils import make_path_relative_to_cwd
from puyapy import interpreter_data
from puyapy.find_sources import ResolvedSource, create_source_list

logger = log.get_logger(__name__)

# this should contain the lowest version number that this compiler does NOT support
# i.e. the next minor version after what is defined in stubs/pyproject.toml:project.version
MAX_SUPPORTED_ALGOPY_VERSION_EX = version.parse("3.1.0")
MIN_SUPPORTED_ALGOPY_VERSION = version.parse(f"{MAX_SUPPORTED_ALGOPY_VERSION_EX.major}.0.0")


class SourceDiscoveryMechanism(enum.Enum):
    explicit = enum.auto()
    dependency = enum.auto()


@attrs.frozen
class SourceModule:
    name: str
    node: MypyFile
    path: Path
    lines: Sequence[str] | None
    discovery_mechanism: SourceDiscoveryMechanism
    is_typeshed_file: bool
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
            if sm.discovery_mechanism != SourceDiscoveryMechanism.dependency
        }


def parse_python(
    paths: Sequence[Path],
    *,
    package_search_paths: Sequence[str] | typing.Literal["infer", "current"] = "current",
    file_contents: Mapping[Path, str] | None = None,
    excluded_subdir_names: Sequence[str] | None = None,
) -> ParseResult:
    """Generate the ASTs from the build sources, and all imported modules (recursively)"""

    sources_by_module_name = _create_and_check_source_list(
        paths, excluded_subdir_names=excluded_subdir_names
    )
    source_roots = [bs.base_dir for bs in sources_by_module_name.values()]
    source_roots.append(Path.cwd())

    python_path = tuple(dict.fromkeys(map(str, source_roots)))
    package_paths = tuple(_resolve_package_paths(package_search_paths))
    typeshed_paths = _typeshed_paths()
    mypy_search_paths = SearchPaths(
        python_path=python_path,
        package_path=package_paths,
        typeshed_path=typeshed_paths,
        mypy_path=(),
    )
    mypy_build_sources = [
        BuildSource(path=str(bs.path), module=module_name, base_dir=str(bs.base_dir))
        for module_name, bs in sorted(sources_by_module_name.items(), key=itemgetter(0))
    ]
    mypy_options = _get_mypy_options()
    fs_cache = FileSystemCache()
    # prime the cache with supplied content overrides, so that mypy reads from our data instead
    if file_contents:
        for content_path, content in file_contents.items():
            fn = str(content_path)
            data = content.encode("utf-8")
            fs_cache.stat_or_none(fn)
            fs_cache.read_cache[fn] = data
            fs_cache.hash_cache[fn] = hash_digest(data)

    manager, graph = _mypy_build(mypy_build_sources, mypy_options, mypy_search_paths, fs_cache)
    # Sometimes when we call back into mypy, there might be errors.
    # We don't want to crash when that happens.
    manager.errors.set_file("<puyapy>", module=None, scope=None, options=mypy_options)
    missing_module_names = sources_by_module_name.keys() - manager.modules.keys()
    # Note: this shouldn't happen, provided we've successfully disabled the mypy cache
    assert (
        not missing_module_names
    ), f"mypy parse failed, missing modules: {', '.join(missing_module_names)}"

    # order modules by dependency, and also sanity check the contents
    ordered_modules = {}
    for scc_module_names in sorted_components(graph):
        for module_name in scc_module_names:
            module = manager.modules[module_name]
            state = graph[module_name]
            assert (
                module_name == module.fullname
            ), f"mypy module mismatch, expected {module_name}, got {module.fullname}"
            assert module.path, f"no path for mypy module: {module_name}"
            module_path = Path(module.path).resolve()
            if module_path.is_dir():
                # this module is a module directory with no __init__.py, ie it contains
                # nothing and is only in the graph as a reference
                pass
            else:
                _check_encoding(fs_cache, module_path)
                lines = read_py_file(str(module_path), fs_cache.read)
                if module_name in sources_by_module_name:
                    discovery_mechanism = SourceDiscoveryMechanism.explicit
                else:
                    discovery_mechanism = SourceDiscoveryMechanism.dependency
                ordered_modules[module_name] = SourceModule(
                    name=module_name,
                    node=module,
                    path=module_path,
                    lines=lines,
                    discovery_mechanism=discovery_mechanism,
                    is_typeshed_file=module.is_typeshed_file(mypy_options),
                    dependencies=frozenset(state.dependencies_set),
                )

    return ParseResult(mypy_options=mypy_options, ordered_modules=ordered_modules)


def _create_and_check_source_list(
    paths: Sequence[Path],
    *,
    excluded_subdir_names: Sequence[str] | None,
) -> Mapping[str, ResolvedSource]:
    build_sources = create_source_list(paths=paths, excluded_subdir_names=excluded_subdir_names)
    sources_by_module_name = dict[str, ResolvedSource]()
    sources_by_path = dict[Path, ResolvedSource]()
    duplicate_errors = list[ConfigurationError]()
    for bs in build_sources:
        existing = sources_by_module_name.setdefault(bs.module, bs)
        if existing != bs:
            duplicate_errors.append(
                ConfigurationError(
                    f"duplicate modules named in build sources:"
                    f" {make_path_relative_to_cwd(bs.path)} has same module name '{bs.module}'"
                    f" as {make_path_relative_to_cwd(existing.path)}"
                )
            )
        else:
            existing = sources_by_path.setdefault(bs.path, bs)
            if existing != bs:
                duplicate_errors.append(
                    ConfigurationError(
                        f"source path {make_path_relative_to_cwd(bs.path)}"
                        f" was resolved to multiple module names, ensure each path is only"
                        f" specified once or add top-level __init__.py files to mark package roots"
                    )
                )
    if duplicate_errors:
        raise ExceptionGroup("duplicate module errors", duplicate_errors)
    return sources_by_module_name


def _resolve_package_paths(
    package_search_paths: Sequence[str] | typing.Literal["infer", "current"],
) -> list[str]:
    match package_search_paths:
        case "current":
            sys_path = interpreter_data.get_sys_path()
        case "infer":
            sys_path = _infer_sys_path()
        case paths:
            sys_path = [os.path.abspath(p) for p in paths]  # noqa: PTH100
    logger.info(f"using python search path: {sys_path}")
    _check_algopy_version(sys_path)
    return sys_path


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


def _check_encoding(mypy_fscache: FileSystemCache, module_path: Path) -> None:
    module_rel_path = make_path_relative_to_cwd(module_path)
    module_loc = SourceLocation(file=module_path, line=1)
    try:
        source = mypy_fscache.read(str(module_path))
    except OSError:
        logger.warning(
            f"Couldn't read source for {module_rel_path}",
            location=module_loc,
        )
        return
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

    return mypy_opts


def _mypy_build(
    sources: list[BuildSource],
    options: MypyOptions,
    search_paths: SearchPaths,
    fscache: FileSystemCache,
) -> tuple[BuildManager, Graph]:
    """Simple wrapper around mypy.build.build

    Makes it so that check errors and parse errors are handled the same (ie with an exception)
    """

    source_set = BuildSourceSet(sources)
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
    process_graph(graph, manager)
    type_state.reset_all_subtype_caches()
    return manager, graph


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
def _typeshed_paths() -> tuple[str, str]:
    """Return default standard library search paths. Guaranteed to be normalised."""
    custom_typeshed_dir = _CUSTOM_TYPESHED_PATH.resolve()
    typeshed_dir = custom_typeshed_dir / "stdlib"
    versions_file = typeshed_dir / "VERSIONS"
    if not typeshed_dir.is_dir() or not versions_file.is_file():
        raise InternalError("puyapy install is corrupted - missing typeshed directories")
    # Get mypy-extensions stubs from typeshed, since we treat it as an
    # "internal" library, similar to typing and typing-extensions.
    mypy_extensions_dir = custom_typeshed_dir / "stubs" / "mypy-extensions"
    return str(typeshed_dir), str(mypy_extensions_dir)


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
