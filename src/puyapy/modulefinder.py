import enum
import os

from mypy.fscache import FileSystemCache
from mypy.modulefinder import BuildSource, BuildSourceSet, SearchPaths
from mypy.options import Options
from mypy.util import os_path_join

# Package dirs are a two-tuple of path to search and whether to verify the module
OnePackageDir = tuple[str, bool]
PackageDirs = list[OnePackageDir]


@enum.unique
class ModuleNotFoundReason(enum.Enum):
    # The module was not found: we found neither stubs nor a plausible code
    # implementation (with or without a py.typed file).
    NOT_FOUND = 0

    # The implementation for this module plausibly exists (e.g. we
    # found a matching folder or *.py file), but the parent package
    # did not contain a py.typed file
    NO_TYPED_MARKER = 1


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
        options: Options,
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
                if not self.fscache.isfile(os_path_join(d, "__init__.py")):
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
            if not parent.endswith("__init__.py") and (
                ext == ".py" and not self.fscache.isdir(basename)
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

    def find_module(self, id: str) -> ModuleSearchResult:
        """Return the path of the module source file or why it wasn't found.

        If fast_path is True, prioritize performance over generating detailed
        error descriptions.
        """
        if id not in self.results:
            result, should_cache = self._find_module(id)
            if should_cache:
                self.results[id] = result
            return result
        return self.results[id]

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
            return ModuleNotFoundReason.NO_TYPED_MARKER
        else:
            return ModuleNotFoundReason.NOT_FOUND

    def _update_ns_ancestors(self, components: list[str], match: tuple[str, bool]) -> None:
        path, verify = match
        for i in range(1, len(components)):
            pkg_id = ".".join(components[:-i])
            if pkg_id not in self.ns_ancestors and self.fscache.isdir(path):
                self.ns_ancestors[pkg_id] = path
            path = os.path.dirname(path)

    def _find_module(self, id: str) -> tuple[ModuleSearchResult, bool]:
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
        p = self.find_module_via_source_set(id) if self.options.fast_module_lookup else None
        if p:
            return p, True

        # If we're looking for a module like 'foo.bar.baz', it's likely that most of the
        # many elements of lib_path don't even have a subdirectory 'foo/bar'.  Discover
        # that only once and cache it for when we look for modules like 'foo.bar.blah'
        # that will require the same subdirectory.
        components = id.split(".")

        # Third-party stub/typed packages
        candidate_package_dirs = {
            package_dir[0]
            for package_dir in self.find_lib_path_dirs(
                components[0], self.search_paths.package_path
            )
        }

        third_party_inline_dirs: PackageDirs = []
        found_possible_third_party_missing_typed_marker = False
        for pkg_dir in self.search_paths.package_path:
            if pkg_dir in candidate_package_dirs:
                non_stub_match = self._find_module_non_stub_helper(id, pkg_dir)
                if non_stub_match is ModuleNotFoundReason.NO_TYPED_MARKER:
                    found_possible_third_party_missing_typed_marker = True
                elif non_stub_match is not ModuleNotFoundReason.NOT_FOUND:
                    third_party_inline_dirs.append(non_stub_match)
                    self._update_ns_ancestors(components, non_stub_match)

        python_path = self.search_paths.python_path
        candidate_base_dirs = self.find_lib_path_dirs(id, python_path)
        candidate_base_dirs += third_party_inline_dirs

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

            # Prefer package over module, i.e. baz/__init__.py* over baz.py*.
            path = base_path + sepinit + ".py"
            if fscache.isfile_case(path, dir_prefix):
                has_init = True
                if verify and not verify_module(fscache, id, path, dir_prefix):
                    near_misses.append((path, dir_prefix))
                else:
                    return path, True

            # In namespace mode, register a potential namespace package
            if self.options.namespace_packages:
                if (
                    not has_init
                    and fscache.exists_case(base_path, dir_prefix)
                    and not fscache.isfile_case(base_path, dir_prefix)
                ):
                    near_misses.append((base_path, dir_prefix))

            # No package, look for module.
            path = base_path + ".py"
            if fscache.isfile_case(path, dir_prefix):
                if verify and not verify_module(fscache, id, path, dir_prefix):
                    near_misses.append((path, dir_prefix))
                else:
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
        if self.options.namespace_packages and near_misses:
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

        if found_possible_third_party_missing_typed_marker:
            # Caching NO_TYPED_MARKER is not always safe. That causes issues with
            # typed subpackages in namespace packages.
            return ModuleNotFoundReason.NO_TYPED_MARKER, False
        return ModuleNotFoundReason.NOT_FOUND, True

    def find_modules_recursive(self, module: str) -> list[BuildSource]:
        module_path = self.find_module(module)
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

            if self.fscache.isdir(subpath):
                # Only recurse into packages
                if self.options.namespace_packages or (
                    self.fscache.isfile(os_path_join(subpath, "__init__.py"))
                ):
                    seen.add(name)
                    sources.extend(self.find_modules_recursive(module + "." + name))
            else:
                stem, suffix = os.path.splitext(name)
                if stem == "__init__":
                    continue
                if stem not in seen and "." not in stem and suffix == ".py":
                    # (If we sorted names by keyfunc) we could probably just make the BuildSource
                    # ourselves, but this ensures compatibility with find_module / the cache
                    seen.add(stem)
                    sources.extend(self.find_modules_recursive(module + "." + stem))
        return sources


def is_init_file(path: str) -> bool:
    return os.path.basename(path) == "__init__.py"


def verify_module(fscache: FileSystemCache, id: str, path: str, prefix: str) -> bool:
    """Check that all packages containing id have a __init__ file."""
    if is_init_file(path):
        path = os.path.dirname(path)
    for i in range(id.count(".")):
        path = os.path.dirname(path)
        if not fscache.isfile_case(os_path_join(path, "__init__.py"), prefix):
            return False
    return True


def highest_init_level(fscache: FileSystemCache, id: str, path: str, prefix: str) -> int:
    """Compute the highest level where an __init__ file is found."""
    if is_init_file(path):
        path = os.path.dirname(path)
    level = 0
    for i in range(id.count(".")):
        path = os.path.dirname(path)
        if fscache.isfile_case(os_path_join(path, "__init__.py"), prefix):
            level = i + 1
    return level
