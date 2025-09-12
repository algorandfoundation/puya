# ruff: noqa: A002

import functools
import typing
from collections.abc import Sequence
from pathlib import Path

import attrs
from mypy.fscache import FileSystemCache

from puya import log
from puya.errors import ConfigurationError

logger = log.get_logger(__name__)


@attrs.frozen
class BuildSource:
    """A single source file."""

    path: Path
    """File where it's found (e.g. '/home/user/pkg/module.py')"""
    module: str
    """Module name (e.g. 'pkg.module')"""
    base_dir: Path
    """Directory where the package is rooted (e.g. '/home/user')"""


def create_source_list(
    paths: Sequence[Path],
    fscache: FileSystemCache,
    *,
    excluded_subdir_names: Sequence[str] | None = None,
) -> list[BuildSource]:
    finder = SourceFinder(fscache, excluded_subdir_names=excluded_subdir_names or ())

    sources = []
    for path in paths:
        path = path.resolve()
        if not path.stem.isidentifier():
            logger.error(f"invalid python module name: {path.stem} at {path}")
        elif path.suffix == ".py":
            sources.append(finder.file_source(path))
        elif not path.is_dir():
            logger.error(f"path is not a directory or a .py file: {path}")
        else:
            module_name, base_dir = finder.find_package_root(path)
            if not module_name:
                logger.info(f"treating input path {path} as implicit namespace package root")
                module_name = path.name
                base_dir = path.parent
            sub_sources = finder.find_sources_in_dir(
                path, dir_module_name=module_name, base_dir=base_dir
            )
            if not sub_sources:
                logger.error(f"there are no .py files in directory '{path}'")
            else:
                sources.extend(sub_sources)
    return sources


def keyfunc(path: Path) -> tuple[bool, bool, str]:
    """Determines sort order for directory listing.

    The desirable properties are:
    1) foo < foo.pyi < foo.py
    2) __init__.py[i] < foo
    """
    base = path.stem
    return base != "__init__", path.suffix == ".py", base


class SourceFinder:
    def __init__(self, fscache: FileSystemCache, *, excluded_subdir_names: Sequence[str]) -> None:
        self.fscache: typing.Final = fscache
        self.excluded_subdir_names: typing.Final = frozenset(
            (
                *excluded_subdir_names,
                "__pycache__",
                "site-packages",
                "node_modules",
            )
        )

    def find_sources_in_dir(
        self, dir: Path, *, dir_module_name: str, base_dir: Path
    ) -> list[BuildSource]:
        """Given an absolute directory, recursively find all build sources within."""

        assert dir == dir.resolve()
        assert dir.is_dir()

        sources = []

        seen = set[str]()
        entries = sorted(dir.iterdir(), key=keyfunc)
        for path in entries:
            # Skip certain names altogether
            if path.suffix == ".py":
                stem = path.name.removesuffix(".py")
                if stem in seen:
                    logger.warning(
                        f"python file {path} shadowed by module directory with same name"
                    )
                else:
                    seen.add(stem)
                    if stem == "__init__":
                        path_module_name = dir_module_name
                    else:
                        path_module_name = module_join(dir_module_name, stem)
                    sources.append(BuildSource(path, path_module_name, base_dir))
            elif path.name.startswith(".") or path.name in self.excluded_subdir_names:
                pass  # skip hidden directories and also excluded ones
            elif path.is_dir():
                path_module_name = module_join(dir_module_name, path.name)
                sub_sources = self.find_sources_in_dir(
                    path, dir_module_name=path_module_name, base_dir=base_dir
                )
                if sub_sources:
                    seen.add(path.name)
                    sources.extend(sub_sources)

        return sources

    def file_source(self, path: Path) -> BuildSource:
        """Given a .py[i] filename, return module and base directory.

        For example, given "xxx/yyy/foo/bar.py", we might return something like:
        ("foo.bar", "xxx/yyy")

        If namespace packages is off, we crawl upwards until we find a directory without
        an __init__.py

        If namespace packages is on, we crawl upwards until the nearest explicit base directory.
        Failing that, we return one past the highest directory containing an __init__.py

        We won't crawl past directories with invalid package names.
        The base directory returned is an absolute path.
        """
        assert path == path.resolve()
        assert path.suffix == ".py"

        parent = path.parent
        module_name = path.name.removesuffix(".py")

        parent_module, base_dir = self.find_package_root(parent)
        if module_name == "__init__":
            return BuildSource(path, parent_module, base_dir)

        # Note that module_name might not actually be a valid identifier, but that's okay
        # Ignoring this possibility sidesteps some search path confusion
        module = module_join(parent_module, module_name)
        return BuildSource(path, module, base_dir)

    def find_package_root(self, dir: Path) -> tuple[str, Path]:
        return self._find_package_root(dir) or ("", dir)

    @functools.lru_cache  # noqa: B019
    def _find_package_root(self, dir: Path) -> tuple[str, Path] | None:
        """Given a directory, maybe returns module and base directory.

        We return a non-None value if we were able to find something clearly intended as a base
        directory (as adjudicated by being an explicit base directory or by containing a package
        with __init__.py).

        This distinction is necessary for namespace packages, so that we know when to treat
        ourselves as a subpackage.
        """
        parent = dir.parent
        if parent == dir:
            if (dir / "__init__.py").is_file():
                raise ConfigurationError("root directory cannot be a Python package")
            return None

        name = dir.name
        if name.endswith("-stubs"):  # PEP-561 stub-only directory, not supported
            return None
        elif (dir / "__init__.py").is_file():
            if not name.isidentifier():
                # in most cases the directory name is invalid, we'll just stop crawling upwards
                # but if there's an __init__.py in the directory, something is messed up
                raise ConfigurationError(f"{name} is not a valid Python package name")
            mod_prefix, base_dir = self.find_package_root(parent)
            return module_join(mod_prefix, name), base_dir
        elif name.isidentifier():
            result = self._find_package_root(parent)
            if result:
                mod_prefix, base_dir = result
                return module_join(mod_prefix, name), base_dir
        return None


def module_join(parent: str, child: str) -> str:
    """Join module ids, accounting for a possibly empty parent."""
    if parent:
        return parent + "." + child
    return child
