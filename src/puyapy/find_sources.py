from collections.abc import Mapping, Sequence
from functools import cached_property
from pathlib import Path

import attrs

from puya import log
from puya.errors import ConfigurationError
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault, make_path_relative_to_cwd, set_add

logger = log.get_logger(__name__)


@attrs.frozen
class ResolvedSource:
    path: Path
    """File where it's found (e.g. '/home/user/pkg/module.py')"""
    module: str = attrs.field()
    """Module name (e.g. 'pkg.module')"""
    base_dir: Path | None
    """
    Directory where the package is rooted (e.g. '/home/user'),
    If None, then unable to determine a package.
    """

    @module.validator
    def _module_validator(self, _attr: object, module: str) -> None:
        if not all(part.isidentifier() for part in module.split(".")):
            logger.warning(
                f'python module name is invalid ("{module}")',
                location=SourceLocation(file=self.path, line=1),
            )


@attrs.frozen
class ResolvedSourceSet:
    sources: Sequence[ResolvedSource]
    sources_by_module_name: Mapping[str, ResolvedSource]
    package_roots: Mapping[str, Path]


def resolve_source_set(
    paths: Sequence[Path], *, excluded_subdir_names: Sequence[str] | None
) -> ResolvedSourceSet:
    resolve_source_list = _create_source_list(paths, excluded_subdir_names=excluded_subdir_names)
    return _create_and_check_source_set(resolve_source_list)


def _create_source_list(
    paths: Sequence[Path], *, excluded_subdir_names: Sequence[str] | None
) -> list[ResolvedSource]:
    finder = _SourceResolver(excluded_subdir_names=excluded_subdir_names)

    sources = []
    for path in paths:
        path = path.resolve()
        if path.suffixes == [".py"]:
            sources.append(finder.file_source(path))
        elif not path.is_dir():
            logger.error(
                f"path is not a directory or a .py file: {make_path_relative_to_cwd(path)}"
            )
        else:
            sub_sources = finder.directory_sources(path)
            if not sub_sources:
                logger.error(
                    f"there are no .py files in directory: {make_path_relative_to_cwd(path)}"
                )
            else:
                sources.extend(sub_sources)
    return sources


@attrs.frozen(kw_only=True)
class _SourceResolver:
    _package_root_cache: dict[Path, tuple[str, Path] | None] = attrs.field(
        factory=dict, init=False
    )
    excluded_subdir_names: Sequence[str] | None = None

    @cached_property
    def _all_excluded_subdir_names(self) -> frozenset[str]:
        return frozenset(
            (
                *(self.excluded_subdir_names or ()),
                "__pycache__",
                "site-packages",
                "node_modules",
            )
        )

    def file_source(self, path: Path) -> ResolvedSource:
        parent = path.parent
        root = self._find_package_root(parent)
        if root is not None:
            parent_module, base_dir = root
        else:
            logger.warning(f"cannot determine package root for {make_path_relative_to_cwd(path)}")
            parent_module = ""
            base_dir = None

        module = _module_join(parent_module, path.stem)
        return ResolvedSource(path, module, base_dir)

    def directory_sources(self, src_dir: Path) -> list[ResolvedSource]:
        """Given an absolute directory, recursively find all build sources within."""
        sources = []
        dir_names = set[str]()
        # sort to ensure that directories appear before any python modules they might shadow
        for path in sorted(src_dir.iterdir()):
            if path.is_dir():
                dir_names.add(path.name)
                if path.name.startswith(".") or path.name in self._all_excluded_subdir_names:
                    pass  # skip hidden directories and also excluded ones
                else:
                    sources.extend(self.directory_sources(path))
            elif path.suffixes == [".py"]:
                if path.stem in dir_names:
                    logger.error(
                        f"python file {make_path_relative_to_cwd(path)}"
                        f" potentially shadowed by directory with same name"
                    )
                else:
                    sources.append(self.file_source(path))
        return sources

    def _find_package_root(self, src_dir: Path) -> tuple[str, Path] | None:
        return lazy_setdefault(
            self._package_root_cache, src_dir, self._find_package_root_recursive
        )

    def _find_package_root_recursive(self, src_dir: Path) -> tuple[str, Path] | None:
        has_init = (src_dir / "__init__.py").is_file()

        parent = src_dir.parent
        if parent == src_dir:  # prevents infinite recursion
            if has_init:  # pragma: no cover
                # no simple cross-platform way to test this without
                # root privileges or an in-process filesystem fake
                logger.error("root directory cannot be a Python package")
            return None

        name = src_dir.name
        if not (has_init or name.isidentifier()):
            # if the directory name is invalid and there's not __init__.py, stop crawling upwards
            return None

        root = self._find_package_root(parent)
        if root is not None:
            mod_prefix, base_dir = root
            return _module_join(mod_prefix, name), base_dir
        elif has_init:
            return name, parent
        else:
            return None


def _module_join(parent: str, child: str) -> str:
    """Join module ids, accounting for a possibly empty parent and/or __init__ child."""
    if parent:
        if child == "__init__":
            return parent
        return parent + "." + child
    return child


def _create_and_check_source_set(
    resolved_sources: Sequence[ResolvedSource],
) -> ResolvedSourceSet:
    """
    Validate the consistency and uniqueness of all properties of resolved sources,
    and return a ResolvedSourceSet..
    """
    sources_by_module_name = dict[str, ResolvedSource]()
    seen_paths = set[Path]()
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
        assert set_add(seen_paths, rs.path), f"duplicate path with different module: {rs.path}"
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
    return ResolvedSourceSet(
        sources=resolved_sources,
        sources_by_module_name=sources_by_module_name,
        package_roots=package_roots,
    )
