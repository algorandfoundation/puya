import functools
import os
import typing
from collections.abc import Sequence

from mypy.fscache import FileSystemCache
from mypy.modulefinder import (
    PYTHON_EXTENSIONS,
    BuildSource,
    matches_exclude,
)

PY_EXTENSIONS: typing.Final = tuple(PYTHON_EXTENSIONS)


class InvalidSourceList(Exception):
    """Exception indicating a problem in the list of sources given to mypy."""


def create_source_list(
    paths: Sequence[str],
    fscache: FileSystemCache,
    *,
    exclude: Sequence[str] | None = None,
) -> list[BuildSource]:
    """From a list of source files/directories, makes a list of BuildSources.

    Raises InvalidSourceList on errors.
    """
    finder = SourceFinder(fscache, exclude=exclude or ())

    sources = []
    for path in paths:
        path = os.path.normpath(path)
        if path.endswith(PY_EXTENSIONS):
            # Can raise InvalidSourceList if a directory doesn't have a valid module name.
            name, base_dir = finder.crawl_up(path)
            sources.append(BuildSource(path, name, None, base_dir))
        elif fscache.isdir(path):
            sub_sources = finder.find_sources_in_dir(path)
            if not sub_sources:
                raise InvalidSourceList(f"There are no .py[i] files in directory '{path}'")
            sources.extend(sub_sources)
        else:
            # TODO: warn, explicitly named file with unrecognised file extension
            sources.append(BuildSource(path, None, None))
    return sources


def keyfunc(name: str) -> tuple[bool, int, str]:
    """Determines sort order for directory listing.

    The desirable properties are:
    1) foo < foo.pyi < foo.py
    2) __init__.py[i] < foo
    """
    base, suffix = os.path.splitext(name)
    for i, ext in enumerate(PY_EXTENSIONS):
        if suffix == ext:
            return base != "__init__", i, base
    return base != "__init__", -1, name


class SourceFinder:
    def __init__(self, fscache: FileSystemCache, *, exclude: Sequence[str]) -> None:
        self.fscache: typing.Final = fscache
        self.exclude: typing.Final = list(exclude)

    def find_sources_in_dir(self, path: str) -> list[BuildSource]:
        sources = []

        seen = set[str]()
        names = sorted(self.fscache.listdir(path), key=keyfunc)
        for name in names:
            # Skip certain names altogether
            if name in ("__pycache__", "site-packages", "node_modules") or name.startswith("."):
                continue
            subpath = os.path.join(path, name)

            if matches_exclude(subpath, self.exclude, self.fscache, verbose=False):
                continue

            if self.fscache.isdir(subpath):
                sub_sources = self.find_sources_in_dir(subpath)
                if sub_sources:
                    seen.add(name)
                    sources.extend(sub_sources)
            else:
                stem, suffix = os.path.splitext(name)
                if stem not in seen and suffix in PY_EXTENSIONS:
                    seen.add(stem)
                    module, base_dir = self.crawl_up(subpath)
                    sources.append(BuildSource(subpath, module, None, base_dir))

        return sources

    def crawl_up(self, path: str) -> tuple[str, str]:
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
        path = os.path.abspath(path)
        parent, filename = os.path.split(path)

        module_name = strip_py(filename) or filename

        parent_module, base_dir = self.crawl_up_dir(parent)
        if module_name == "__init__":
            return parent_module, base_dir

        # Note that module_name might not actually be a valid identifier, but that's okay
        # Ignoring this possibility sidesteps some search path confusion
        module = module_join(parent_module, module_name)
        return module, base_dir

    def crawl_up_dir(self, dir: str) -> tuple[str, str]:
        return self._crawl_up_helper(dir) or ("", dir)

    @functools.lru_cache  # noqa: B019
    def _crawl_up_helper(self, dir: str) -> tuple[str, str] | None:
        """Given a directory, maybe returns module and base directory.

        We return a non-None value if we were able to find something clearly intended as a base
        directory (as adjudicated by being an explicit base directory or by containing a package
        with __init__.py).

        This distinction is necessary for namespace packages, so that we know when to treat
        ourselves as a subpackage.
        """
        parent, name = os.path.split(dir)
        name = name.removesuffix("-stubs")  # PEP-561 stub-only directory

        # recurse if there's an __init__.py
        init_file = self.get_init_file(dir)
        if init_file is not None:
            if not name.isidentifier():
                # in most cases the directory name is invalid, we'll just stop crawling upwards
                # but if there's an __init__.py in the directory, something is messed up
                raise InvalidSourceList(f"{name} is not a valid Python package name")
            # we're definitely a package, so we always return a non-None value
            mod_prefix, base_dir = self.crawl_up_dir(parent)
            return module_join(mod_prefix, name), base_dir

        # stop crawling if we're out of path components or our name is an invalid identifier
        if not name or not parent or not name.isidentifier():
            return None

        # at this point: namespace packages is on, we don't have an __init__.py and we're not an
        # explicit base directory
        result = self._crawl_up_helper(parent)
        if result is None:
            # we're not an explicit base directory and we don't have an __init__.py
            # and none of our parents are either, so return
            return None
        # one of our parents was an explicit base directory or had an __init__.py, so we're
        # definitely a subpackage! chain our name to the module.
        mod_prefix, base_dir = result
        return module_join(mod_prefix, name), base_dir

    def get_init_file(self, dir: str) -> str | None:
        """Check whether a directory contains a file named __init__.py[i].

        If so, return the file's name (with dir prefixed).  If not, return None.

        This prefers .pyi over .py (because of the ordering of PY_EXTENSIONS).
        """
        for ext in PY_EXTENSIONS:
            f = os.path.join(dir, "__init__" + ext)
            if self.fscache.isfile(f):
                return f
            if ext == ".py" and self.fscache.init_under_package_root(f):
                return f
        return None


def module_join(parent: str, child: str) -> str:
    """Join module ids, accounting for a possibly empty parent."""
    if parent:
        return parent + "." + child
    return child


def strip_py(arg: str) -> str | None:
    """Strip a trailing .py or .pyi suffix.

    Return None if no such suffix is found.
    """
    for ext in PY_EXTENSIONS:
        if arg.endswith(ext):
            return arg.removesuffix(ext)
    return None
