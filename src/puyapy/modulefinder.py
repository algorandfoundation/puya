import enum
import functools
import os
import re
import sys
import typing

from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.options import Options
from mypy.stubinfo import stub_distribution_name
from mypy.util import os_path_join
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPatternError

# Package dirs are a two-tuple of path to search and whether to verify the module
OnePackageDir = tuple[str, bool]
PackageDirs = list[OnePackageDir]

# Minimum and maximum Python versions for modules in stdlib as (major, minor)
StdlibVersions: typing.TypeAlias = dict[str, tuple[tuple[int, int], tuple[int, int] | None]]

PYTHON_EXTENSIONS: typing.Final = [".pyi", ".py"]


# TODO: Consider adding more reasons here?
# E.g. if we deduce a module would likely be found if the user were
# to set the --namespace-packages flag.
@enum.unique
class ModuleNotFoundReason(enum.Enum):
    # The module was not found: we found neither stubs nor a plausible code
    # implementation (with or without a py.typed file).
    NOT_FOUND = 0

    # The implementation for this module plausibly exists (e.g. we
    # found a matching folder or *.py file), but either the parent package
    # did not contain a py.typed file or we were unable to find a
    # corresponding *-stubs package.
    FOUND_WITHOUT_TYPE_HINTS = 1

    # The module was not found in the current working directory, but
    # was able to be found in the parent directory.
    WRONG_WORKING_DIRECTORY = 2

    # Stub PyPI package (typically types-pkgname) known to exist but not installed.
    APPROVED_STUBS_NOT_INSTALLED = 3

    def error_message_templates(self, daemon: bool) -> tuple[str, list[str]]:
        doc_link = "See https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports"
        if self is ModuleNotFoundReason.NOT_FOUND:
            msg = 'Cannot find implementation or library stub for module named "{module}"'
            notes = [doc_link]
        elif self is ModuleNotFoundReason.WRONG_WORKING_DIRECTORY:
            msg = 'Cannot find implementation or library stub for module named "{module}"'
            notes = [
                "You may be running mypy in a subpackage, mypy should be run on the package root"
            ]
        elif self is ModuleNotFoundReason.FOUND_WITHOUT_TYPE_HINTS:
            msg = (
                'Skipping analyzing "{module}": module is installed, but missing library stubs '
                "or py.typed marker"
            )
            notes = [doc_link]
        elif self is ModuleNotFoundReason.APPROVED_STUBS_NOT_INSTALLED:
            msg = 'Library stubs not installed for "{module}"'
            notes = ['Hint: "python3 -m pip install {stub_dist}"']
            if not daemon:
                notes.append(
                    '(or run "mypy --install-types" to install all missing stub packages)'
                )
            notes.append(doc_link)
        else:
            assert False
        return msg, notes


# If we found the module, returns the path to the module as a str.
# Otherwise, returns the reason why the module wasn't found.
ModuleSearchResult = str | ModuleNotFoundReason


class FindModuleCache:
    """Module finder with integrated cache.

    Module locations and some intermediate results are cached internally
    and can be cleared with the clear() method.

    All file system accesses are performed through a FileSystemCache,
    which is not ever cleared by this class. If necessary it must be
    cleared by client code.
    """

    def __init__(
        self,
        search_paths: SearchPaths,
        fscache: FileSystemCache | None,
        options: Options | None,
        stdlib_py_versions: StdlibVersions | None = None,
        source_set: BuildSourceSet | None = None,
    ) -> None:
        self.search_paths = search_paths
        self.source_set = source_set
        self.fscache = fscache or FileSystemCache()
        # Cache for get_toplevel_possibilities:
        # search_paths -> (toplevel_id -> list(package_dirs))
        self.initial_components: dict[tuple[str, ...], dict[str, list[str]]] = {}
        # Cache find_module: id -> result
        self.results: dict[str, ModuleSearchResult] = {}
        self.ns_ancestors: dict[str, str] = {}
        self.options = options
        custom_typeshed_dir = None
        if options:
            custom_typeshed_dir = options.custom_typeshed_dir
        self.stdlib_py_versions = stdlib_py_versions or load_stdlib_py_versions(
            custom_typeshed_dir
        )

    def clear(self) -> None:
        self.results.clear()
        self.initial_components.clear()
        self.ns_ancestors.clear()

    def find_module_via_source_set(self, id: str) -> ModuleSearchResult | None:
        """Fast path to find modules by looking through the input sources

        This is only used when --fast-module-lookup is passed on the command line."""
        if not self.source_set:
            return None

        p = self.source_set.source_modules.get(id, None)
        if p and self.fscache.isfile(p):
            # We need to make sure we still have __init__.py all the way up
            # otherwise we might have false positives compared to slow path
            # in case of deletion of init files, which is covered by some tests.
            # TODO: are there some combination of flags in which this check should be skipped?
            d = os.path.dirname(p)
            for _ in range(id.count(".")):
                if not any(
                    self.fscache.isfile(os_path_join(d, "__init__" + x)) for x in PYTHON_EXTENSIONS
                ):
                    return None
                d = os.path.dirname(d)
            return p

        idx = id.rfind(".")
        if idx != -1:
            # When we're looking for foo.bar.baz and can't find a matching module
            # in the source set, look up for a foo.bar module.
            parent = self.find_module_via_source_set(id[:idx])
            if parent is None or not isinstance(parent, str):
                return None

            basename, ext = os.path.splitext(parent)
            if not any(parent.endswith("__init__" + x) for x in PYTHON_EXTENSIONS) and (
                ext in PYTHON_EXTENSIONS and not self.fscache.isdir(basename)
            ):
                # If we do find such a *module* (and crucially, we don't want a package,
                # hence the filtering out of __init__ files, and checking for the presence
                # of a folder with a matching name), then we can be pretty confident that
                # 'baz' will either be a top-level variable in foo.bar, or will not exist.
                #
                # Either way, spelunking in other search paths for another 'foo.bar.baz'
                # module should be avoided because:
                #  1. in the unlikely event that one were found, it's highly likely that
                #     it would be unrelated to the source being typechecked and therefore
                #     more likely to lead to erroneous results
                #  2. as described in _find_module, in some cases the search itself could
                #  potentially waste significant amounts of time
                return ModuleNotFoundReason.NOT_FOUND
        return None

    def find_lib_path_dirs(self, id: str, lib_path: tuple[str, ...]) -> PackageDirs:
        """Find which elements of a lib_path have the directory a module needs to exist."""
        components = id.split(".")
        dir_chain = os.sep.join(components[:-1])  # e.g., 'foo/bar'

        dirs = []
        for pathitem in self.get_toplevel_possibilities(lib_path, components[0]):
            # e.g., '/usr/lib/python3.4/foo/bar'
            if dir_chain:
                dir = os_path_join(pathitem, dir_chain)
            else:
                dir = pathitem
            if self.fscache.isdir(dir):
                dirs.append((dir, True))
        return dirs

    def get_toplevel_possibilities(self, lib_path: tuple[str, ...], id: str) -> list[str]:
        """Find which elements of lib_path could contain a particular top-level module.

        In practice, almost all modules can be routed to the correct entry in
        lib_path by looking at just the first component of the module name.

        We take advantage of this by enumerating the contents of all of the
        directories on the lib_path and building a map of which entries in
        the lib_path could contain each potential top-level module that appears.
        """

        if lib_path in self.initial_components:
            return self.initial_components[lib_path].get(id, [])

        # Enumerate all the files in the directories on lib_path and produce the map
        components: dict[str, list[str]] = {}
        for dir in lib_path:
            try:
                contents = self.fscache.listdir(dir)
            except OSError:
                contents = []
            # False positives are fine for correctness here, since we will check
            # precisely later, so we only look at the root of every filename without
            # any concern for the exact details.
            for name in contents:
                name = os.path.splitext(name)[0]
                components.setdefault(name, []).append(dir)

        self.initial_components[lib_path] = components
        return components.get(id, [])

    def find_module(self, id: str, *, fast_path: bool = False) -> ModuleSearchResult:
        """Return the path of the module source file or why it wasn't found.

        If fast_path is True, prioritize performance over generating detailed
        error descriptions.
        """
        if id not in self.results:
            top_level = id.partition(".")[0]
            use_typeshed = True
            if id in self.stdlib_py_versions:
                use_typeshed = self._typeshed_has_version(id)
            elif top_level in self.stdlib_py_versions:
                use_typeshed = self._typeshed_has_version(top_level)
            result, should_cache = self._find_module(id, use_typeshed)
            if should_cache:
                if (
                    not (
                        fast_path or (self.options is not None and self.options.fast_module_lookup)
                    )
                    and result is ModuleNotFoundReason.NOT_FOUND
                    and self._can_find_module_in_parent_dir(id)
                ):
                    self.results[id] = ModuleNotFoundReason.WRONG_WORKING_DIRECTORY
                else:
                    self.results[id] = result
                return self.results[id]
            else:
                return result
        return self.results[id]

    def _typeshed_has_version(self, module: str) -> bool:
        if not self.options:
            return True
        version = typeshed_py_version(self.options)
        min_version, max_version = self.stdlib_py_versions[module]
        return version >= min_version and (max_version is None or version <= max_version)

    def _find_module_non_stub_helper(
        self, id: str, pkg_dir: str
    ) -> OnePackageDir | ModuleNotFoundReason:
        plausible_match = False
        dir_path = pkg_dir
        components = id.split(".")
        for index, component in enumerate(components):
            dir_path = os_path_join(dir_path, component)
            if self.fscache.isfile(os_path_join(dir_path, "py.typed")):
                return os.path.join(pkg_dir, *components[:-1]), index == 0
            elif not plausible_match and (
                self.fscache.isdir(dir_path) or self.fscache.isfile(dir_path + ".py")
            ):
                plausible_match = True
            # If this is not a directory then we can't traverse further into it
            if not self.fscache.isdir(dir_path):
                break
        if plausible_match:
            if self.options:
                module_specific_options = self.options.clone_for_module(id)
                if module_specific_options.follow_untyped_imports:
                    return os.path.join(pkg_dir, *components[:-1]), False
            return ModuleNotFoundReason.FOUND_WITHOUT_TYPE_HINTS
        else:
            return ModuleNotFoundReason.NOT_FOUND

    def _update_ns_ancestors(self, components: list[str], match: tuple[str, bool]) -> None:
        path, verify = match
        for i in range(1, len(components)):
            pkg_id = ".".join(components[:-i])
            if pkg_id not in self.ns_ancestors and self.fscache.isdir(path):
                self.ns_ancestors[pkg_id] = path
            path = os.path.dirname(path)

    def _can_find_module_in_parent_dir(self, id: str) -> bool:
        """Test if a module can be found by checking the parent directories
        of the current working directory.
        """
        working_dir = os.getcwd()
        parent_search = FindModuleCache(
            SearchPaths((), (), (), ()),
            self.fscache,
            self.options,
            stdlib_py_versions=self.stdlib_py_versions,
        )
        while any(is_init_file(file) for file in os.listdir(working_dir)):
            working_dir = os.path.dirname(working_dir)
            parent_search.search_paths = SearchPaths((working_dir,), (), (), ())
            if not isinstance(parent_search._find_module(id, False)[0], ModuleNotFoundReason):
                return True
        return False

    def _find_module(self, id: str, use_typeshed: bool) -> tuple[ModuleSearchResult, bool]:
        """Try to find a module in all available sources.

        Returns:
            ``(result, can_be_cached)`` pair.
        """
        fscache = self.fscache

        # Fast path for any modules in the current source set.
        # This is particularly important when there are a large number of search
        # paths which share the first (few) component(s) due to the use of namespace
        # packages, for instance:
        # foo/
        #    company/
        #        __init__.py
        #        foo/
        # bar/
        #    company/
        #        __init__.py
        #        bar/
        # baz/
        #    company/
        #        __init__.py
        #        baz/
        #
        # mypy gets [foo/company/foo, bar/company/bar, baz/company/baz, ...] as input
        # and computes [foo, bar, baz, ...] as the module search path.
        #
        # This would result in O(n) search for every import of company.*, leading to
        # O(n**2) behavior in load_graph as such imports are unsurprisingly present
        # at least once, and usually many more times than that, in each and every file
        # being parsed.
        #
        # Thankfully, such cases are efficiently handled by looking up the module path
        # via BuildSourceSet.
        p = (
            self.find_module_via_source_set(id)
            if (self.options is not None and self.options.fast_module_lookup)
            else None
        )
        if p:
            return p, True

        # If we're looking for a module like 'foo.bar.baz', it's likely that most of the
        # many elements of lib_path don't even have a subdirectory 'foo/bar'.  Discover
        # that only once and cache it for when we look for modules like 'foo.bar.blah'
        # that will require the same subdirectory.
        components = id.split(".")
        dir_chain = os.sep.join(components[:-1])  # e.g., 'foo/bar'

        # We have two sets of folders so that we collect *all* stubs folders and
        # put them in the front of the search path
        third_party_inline_dirs: PackageDirs = []
        third_party_stubs_dirs: PackageDirs = []
        found_possible_third_party_missing_type_hints = False
        # Third-party stub/typed packages
        candidate_package_dirs = {
            package_dir[0]
            for component in (components[0], components[0] + "-stubs")
            for package_dir in self.find_lib_path_dirs(component, self.search_paths.package_path)
        }
        # Caching FOUND_WITHOUT_TYPE_HINTS is not always safe. That causes issues with
        # typed subpackages in namespace packages.
        can_cache_any_result = True
        for pkg_dir in self.search_paths.package_path:
            if pkg_dir not in candidate_package_dirs:
                continue
            stub_name = components[0] + "-stubs"
            stub_dir = os_path_join(pkg_dir, stub_name)
            if fscache.isdir(stub_dir):
                stub_typed_file = os_path_join(stub_dir, "py.typed")
                stub_components = [stub_name] + components[1:]
                path = os.path.join(pkg_dir, *stub_components[:-1])
                if fscache.isdir(path):
                    if fscache.isfile(stub_typed_file):
                        # Stub packages can have a py.typed file, which must include
                        # 'partial\n' to make the package partial
                        # Partial here means that mypy should look at the runtime
                        # package if installed.
                        if fscache.read(stub_typed_file).decode().strip() == "partial":
                            runtime_path = os_path_join(pkg_dir, dir_chain)
                            third_party_inline_dirs.append((runtime_path, True))
                            # if the package is partial, we don't verify the module, as
                            # the partial stub package may not have a __init__.pyi
                            third_party_stubs_dirs.append((path, False))
                        else:
                            # handle the edge case where people put a py.typed file
                            # in a stub package, but it isn't partial
                            third_party_stubs_dirs.append((path, True))
                    else:
                        third_party_stubs_dirs.append((path, True))
            non_stub_match = self._find_module_non_stub_helper(id, pkg_dir)
            if isinstance(non_stub_match, ModuleNotFoundReason):
                if non_stub_match is ModuleNotFoundReason.FOUND_WITHOUT_TYPE_HINTS:
                    found_possible_third_party_missing_type_hints = True
                    can_cache_any_result = False
            else:
                third_party_inline_dirs.append(non_stub_match)
                self._update_ns_ancestors(components, non_stub_match)

        if self.options and self.options.use_builtins_fixtures:
            # Everything should be in fixtures.
            third_party_inline_dirs.clear()
            third_party_stubs_dirs.clear()
            found_possible_third_party_missing_type_hints = False
        python_mypy_path = self.search_paths.mypy_path + self.search_paths.python_path
        candidate_base_dirs = self.find_lib_path_dirs(id, python_mypy_path)
        if use_typeshed:
            # Search for stdlib stubs in typeshed before installed
            # stubs to avoid picking up backports (dataclasses, for
            # example) when the library is included in stdlib.
            candidate_base_dirs += self.find_lib_path_dirs(id, self.search_paths.typeshed_path)
        candidate_base_dirs += third_party_stubs_dirs + third_party_inline_dirs

        # If we're looking for a module like 'foo.bar.baz', then candidate_base_dirs now
        # contains just the subdirectories 'foo/bar' that actually exist under the
        # elements of lib_path.  This is probably much shorter than lib_path itself.
        # Now just look for 'baz.pyi', 'baz/__init__.py', etc., inside those directories.
        seplast = os.sep + components[-1]  # so e.g. '/baz'
        sepinit = os.sep + "__init__"
        near_misses = []  # Collect near misses for namespace mode (see below).
        for base_dir, verify in candidate_base_dirs:
            base_path = base_dir + seplast  # so e.g. '/usr/lib/python3.4/foo/bar/baz'
            has_init = False
            dir_prefix = base_dir
            for _ in range(len(components) - 1):
                dir_prefix = os.path.dirname(dir_prefix)

            # Stubs-only packages always take precedence over py.typed packages
            path_stubs = f"{base_path}-stubs{sepinit}.pyi"
            if fscache.isfile_case(path_stubs, dir_prefix):
                if verify and not verify_module(fscache, id, path_stubs, dir_prefix):
                    near_misses.append((path_stubs, dir_prefix))
                else:
                    return path_stubs, True

            # Prefer package over module, i.e. baz/__init__.py* over baz.py*.
            for extension in PYTHON_EXTENSIONS:
                path = base_path + sepinit + extension
                if fscache.isfile_case(path, dir_prefix):
                    has_init = True
                    if verify and not verify_module(fscache, id, path, dir_prefix):
                        near_misses.append((path, dir_prefix))
                        continue
                    return path, True

            # In namespace mode, register a potential namespace package
            if self.options and self.options.namespace_packages:
                if (
                    not has_init
                    and fscache.exists_case(base_path, dir_prefix)
                    and not fscache.isfile_case(base_path, dir_prefix)
                ):
                    near_misses.append((base_path, dir_prefix))

            # No package, look for module.
            for extension in PYTHON_EXTENSIONS:
                path = base_path + extension
                if fscache.isfile_case(path, dir_prefix):
                    if verify and not verify_module(fscache, id, path, dir_prefix):
                        near_misses.append((path, dir_prefix))
                        continue
                    return path, True

        # In namespace mode, re-check those entries that had 'verify'.
        # Assume search path entries xxx, yyy and zzz, and we're
        # looking for foo.bar.baz.  Suppose near_misses has:
        #
        # - xxx/foo/bar/baz.py
        # - yyy/foo/bar/baz/__init__.py
        # - zzz/foo/bar/baz.pyi
        #
        # If any of the foo directories has __init__.py[i], it wins.
        # Else, we look for foo/bar/__init__.py[i], etc.  If there are
        # none, the first hit wins.  Note that this does not take into
        # account whether the lowest-level module is a file (baz.py),
        # a package (baz/__init__.py), or a stub file (baz.pyi) -- for
        # these the first one encountered along the search path wins.
        #
        # The helper function highest_init_level() returns an int that
        # indicates the highest level at which a __init__.py[i] file
        # is found; if no __init__ was found it returns 0, if we find
        # only foo/bar/__init__.py it returns 1, and if we have
        # foo/__init__.py it returns 2 (regardless of what's in
        # foo/bar).  It doesn't look higher than that.
        if self.options and self.options.namespace_packages and near_misses:
            levels = [
                highest_init_level(fscache, id, path, dir_prefix)
                for path, dir_prefix in near_misses
            ]
            index = levels.index(max(levels))
            return near_misses[index][0], True

        # Finally, we may be asked to produce an ancestor for an
        # installed package with a py.typed marker that is a
        # subpackage of a namespace package.  We only fess up to these
        # if we would otherwise return "not found".
        ancestor = self.ns_ancestors.get(id)
        if ancestor is not None:
            return ancestor, True

        approved_dist_name = stub_distribution_name(id)
        if approved_dist_name:
            if len(components) == 1:
                return ModuleNotFoundReason.APPROVED_STUBS_NOT_INSTALLED, True
            # If we're a missing submodule of an already installed approved stubs, we don't want to
            # error with APPROVED_STUBS_NOT_INSTALLED, but rather want to return NOT_FOUND.
            for i in range(1, len(components)):
                parent_id = ".".join(components[:i])
                if stub_distribution_name(parent_id) == approved_dist_name:
                    break
            else:
                return ModuleNotFoundReason.APPROVED_STUBS_NOT_INSTALLED, True
            if self.find_module(parent_id) is ModuleNotFoundReason.APPROVED_STUBS_NOT_INSTALLED:
                return ModuleNotFoundReason.APPROVED_STUBS_NOT_INSTALLED, True
            return ModuleNotFoundReason.NOT_FOUND, True

        if found_possible_third_party_missing_type_hints:
            return ModuleNotFoundReason.FOUND_WITHOUT_TYPE_HINTS, can_cache_any_result
        return ModuleNotFoundReason.NOT_FOUND, True

    def find_modules_recursive(self, module: str) -> list[BuildSource]:
        module_path = self.find_module(module, fast_path=True)
        if isinstance(module_path, ModuleNotFoundReason):
            return []
        sources = [BuildSource(module_path, module, None)]

        package_path = None
        if is_init_file(module_path):
            package_path = os.path.dirname(module_path)
        elif self.fscache.isdir(module_path):
            package_path = module_path
        if package_path is None:
            return sources

        # This logic closely mirrors that in find_sources. One small but important difference is
        # that we do not sort names with keyfunc. The recursive call to find_modules_recursive
        # calls find_module, which will handle the preference between packages, pyi and py.
        # Another difference is it doesn't handle nested search paths / package roots.

        seen: set[str] = set()
        names = sorted(self.fscache.listdir(package_path))
        for name in names:
            # Skip certain names altogether
            if name in ("__pycache__", "site-packages", "node_modules") or name.startswith("."):
                continue
            subpath = os_path_join(package_path, name)

            if self.options and matches_exclude(
                subpath, self.options.exclude, self.fscache, self.options.verbosity >= 2
            ):
                continue
            if (
                self.options
                and self.options.exclude_gitignore
                and matches_gitignore(subpath, self.fscache, self.options.verbosity >= 2)
            ):
                continue

            if self.fscache.isdir(subpath):
                # Only recurse into packages
                if (self.options and self.options.namespace_packages) or (
                    self.fscache.isfile(os_path_join(subpath, "__init__.py"))
                    or self.fscache.isfile(os_path_join(subpath, "__init__.pyi"))
                ):
                    seen.add(name)
                    sources.extend(self.find_modules_recursive(module + "." + name))
            else:
                stem, suffix = os.path.splitext(name)
                if stem == "__init__":
                    continue
                if stem not in seen and "." not in stem and suffix in PYTHON_EXTENSIONS:
                    # (If we sorted names by keyfunc) we could probably just make the BuildSource
                    # ourselves, but this ensures compatibility with find_module / the cache
                    seen.add(stem)
                    sources.extend(self.find_modules_recursive(module + "." + stem))
        return sources


def matches_exclude(
    subpath: str, excludes: list[str], fscache: FileSystemCache, verbose: bool
) -> bool:
    if not excludes:
        return False
    subpath_str = os.path.relpath(subpath).replace(os.sep, "/")
    if fscache.isdir(subpath):
        subpath_str += "/"
    for exclude in excludes:
        try:
            if re.search(exclude, subpath_str):
                if verbose:
                    print(
                        f"TRACE: Excluding {subpath_str} (matches pattern {exclude})",
                        file=sys.stderr,
                    )
                return True
        except re.error as e:
            print(
                f"error: The exclude {exclude} is an invalid regular expression, because: {e}"
                + (
                    "\n(Hint: use / as a path separator, even if you're on Windows!)"
                    if "\\" in exclude
                    else ""
                )
                + "\nFor more information on Python's flavor of regex, see:"
                + " https://docs.python.org/3/library/re.html",
                file=sys.stderr,
            )
            sys.exit(2)
    return False


def matches_gitignore(subpath: str, fscache: FileSystemCache, verbose: bool) -> bool:
    dir, _ = os.path.split(subpath)
    for gi_path, gi_spec in find_gitignores(dir):
        relative_path = os.path.relpath(subpath, gi_path)
        if fscache.isdir(relative_path):
            relative_path = relative_path + "/"
        if gi_spec.match_file(relative_path):
            if verbose:
                print(
                    f"TRACE: Excluding {relative_path} (matches .gitignore) in {gi_path}",
                    file=sys.stderr,
                )
            return True
    return False


@functools.lru_cache
def find_gitignores(dir: str) -> list[tuple[str, PathSpec]]:
    parent_dir = os.path.dirname(dir)
    if parent_dir == dir:
        parent_gitignores = []
    else:
        parent_gitignores = find_gitignores(parent_dir)

    gitignore = os.path.join(dir, ".gitignore")
    if os.path.isfile(gitignore):
        with open(gitignore) as f:
            lines = f.readlines()
        try:
            return parent_gitignores + [(dir, PathSpec.from_lines("gitwildmatch", lines))]
        except GitWildMatchPatternError:
            print(f"error: could not parse {gitignore}", file=sys.stderr)
            return parent_gitignores
    return parent_gitignores


def is_init_file(path: str) -> bool:
    return os.path.basename(path) in ("__init__.py", "__init__.pyi")


def verify_module(fscache: FileSystemCache, id: str, path: str, prefix: str) -> bool:
    """Check that all packages containing id have a __init__ file."""
    if is_init_file(path):
        path = os.path.dirname(path)
    for i in range(id.count(".")):
        path = os.path.dirname(path)
        if not any(
            fscache.isfile_case(os_path_join(path, f"__init__{extension}"), prefix)
            for extension in PYTHON_EXTENSIONS
        ):
            return False
    return True


def highest_init_level(fscache: FileSystemCache, id: str, path: str, prefix: str) -> int:
    """Compute the highest level where an __init__ file is found."""
    if is_init_file(path):
        path = os.path.dirname(path)
    level = 0
    for i in range(id.count(".")):
        path = os.path.dirname(path)
        if any(
            fscache.isfile_case(os_path_join(path, f"__init__{extension}"), prefix)
            for extension in PYTHON_EXTENSIONS
        ):
            level = i + 1
    return level


def load_stdlib_py_versions(custom_typeshed_dir: str | None) -> StdlibVersions:
    """Return dict with minimum and maximum Python versions of stdlib modules.

    The contents look like
    {..., 'secrets': ((3, 6), None), 'symbol': ((2, 7), (3, 9)), ...}

    None means there is no maximum version.
    """
    typeshed_dir = custom_typeshed_dir or os_path_join(os.path.dirname(__file__), "typeshed")
    stdlib_dir = os_path_join(typeshed_dir, "stdlib")
    result = {}

    versions_path = os_path_join(stdlib_dir, "VERSIONS")
    assert os.path.isfile(versions_path), (custom_typeshed_dir, versions_path, __file__)
    with open(versions_path) as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line == "":
                continue
            module, version_range = line.split(":")
            versions = version_range.split("-")
            min_version = parse_version(versions[0])
            max_version = (
                parse_version(versions[1]) if len(versions) >= 2 and versions[1].strip() else None
            )
            result[module] = min_version, max_version
    return result


def parse_version(version: str) -> tuple[int, int]:
    major, minor = version.strip().split(".")
    return int(major), int(minor)


def typeshed_py_version(options: Options) -> tuple[int, int]:
    """Return Python version used for checking whether module supports typeshed."""
    # Typeshed no longer covers Python 3.x versions before 3.9, so 3.9 is
    # the earliest we can support.
    return max(options.python_version, (3, 9))
