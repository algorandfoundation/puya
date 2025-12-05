import codecs
import enum
import graphlib
import sys
import typing
from collections import deque
from collections.abc import Collection, Mapping, Sequence, Set
from functools import cached_property
from importlib import metadata
from pathlib import Path

import attrs
from mypy.fscache import FileSystemCache
from mypy.nodes import MypyFile
from mypy.options import Options as MypyOptions
from mypy.util import decode_python_encoding, find_python_encoding, hash_digest
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
from puyapy.parse_mypy import mypy_parse

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

    resolved_sources = create_source_list(paths=paths, excluded_subdir_names=excluded_subdir_names)
    source_roots = _check_source_list_and_extract_package_roots(resolved_sources)

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
        resolved_sources,
        fs_cache,
        source_roots=source_roots,
        package_cache=package_cache,
    )
    mypy_options, mypy_modules_by_name = mypy_parse(module_data, fs_cache)

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
        mypy_module = mypy_modules_by_name[module_name]
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


def _check_source_list_and_extract_package_roots(
    resolved_sources: Sequence[ResolvedSource],
) -> Mapping[str, Path]:
    sources_by_module_name = dict[str, ResolvedSource]()
    sources_by_path = dict[Path, ResolvedSource]()
    package_roots = dict[str, Path]()
    errors = list[str]()
    seen_pkg_conflicts = set[frozenset[Path]]()
    for rs in resolved_sources:
        existing = sources_by_module_name.setdefault(rs.module, rs)
        if existing != rs:
            errors.append(
                f"duplicate modules named in build sources:"
                f" {make_path_relative_to_cwd(rs.path)} has same module name '{rs.module}'"
                f" as {make_path_relative_to_cwd(existing.path)}"
            )
            continue
        existing = sources_by_path.setdefault(rs.path, rs)
        if existing != rs:
            errors.append(
                f"source path {make_path_relative_to_cwd(rs.path)}"
                f" was resolved to multiple module names, ensure each path is only"
                f" specified once or add top-level __init__.py files to mark package roots"
            )
            continue
        pkg = rs.module.partition(".")[0]
        if rs.base_dir is None:
            pkg_root = rs.path
            assert pkg_root.suffixes == [".py"] and pkg_root.stem != "__init__"
        else:
            pkg_root = rs.base_dir / pkg / "__init__.py"
            assert pkg_root.is_file()
        existing_root = package_roots.setdefault(pkg, pkg_root)
        if existing_root != pkg_root:
            if not set_add(seen_pkg_conflicts, frozenset((existing_root, pkg_root))):
                continue
            conflict_msg = f"module '{rs.module}' appears to be a"
            if rs.base_dir is None:
                conflict_msg += f" standalone module at {make_path_relative_to_cwd(pkg_root)}"
            else:
                conflict_msg += f" package rooted at {make_path_relative_to_cwd(rs.base_dir)}"
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
    return package_roots


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
