from collections.abc import Sequence
from functools import cached_property
from pathlib import Path

import attrs

from puya import log
from puya.errors import InternalError
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault, make_path_relative_to_cwd

logger = log.get_logger(__name__)


@attrs.frozen
class ResolvedSource:
    path: Path
    """File where it's found (e.g. '/home/user/pkg/module.py')"""
    module: str
    """Module name (e.g. 'pkg.module')"""
    base_dir: Path | None
    """
    Directory where the package is rooted (e.g. '/home/user'),
    If None, then unable to determine a package.
    """

    def __attrs_post_init__(self) -> None:
        assert self.path.is_file() and self.path.suffixes == [".py"]
        if self.base_dir is None and "." in self.module:
            raise InternalError(
                f'resolved source has qualified module name "{self.module}" but no base_dir'
            )

        if not all(part.isidentifier() for part in self.module.split(".")):
            logger.warning(
                f'python module name is invalid ("{self.module}")',
                location=SourceLocation(file=self.path, line=1),
            )


def create_source_list(
    paths: Sequence[Path], *, excluded_subdir_names: Sequence[str] | None
) -> list[ResolvedSource]:
    finder = _SourceResolver(excluded_subdir_names=excluded_subdir_names)

    sources = []
    for path in paths:
        path = path.resolve()
        if path.suffixes == [".py"]:
            sources.append(finder.file_source(path))
        elif not path.is_dir():
            logger.error(f"path is not a directory or a .py file: {path}")
        else:
            sub_sources = finder.directory_sources(path)
            if not sub_sources:
                logger.error(f"there are no .py files in directory: {path}")
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
                    # TODO: standardise this error here and in dependency_analysis.py
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
            if has_init:
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
