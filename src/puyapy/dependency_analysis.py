import contextlib
import enum
import typing
from collections.abc import Iterator, Mapping, Sequence
from operator import itemgetter
from pathlib import Path

import attrs

from puya import log
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault
from puyapy import reachability
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.visitors.traversers import StatementTraverser

logger = log.get_logger(__name__)


_ALLOWED_STDLIB_STUBS: typing.Final = frozenset(
    (
        "abc",
        "typing",
        # not technically stlib, but treated as synonym for typing for our purposes
        "typing_extensions",
    )
)


@enum.unique
class PackageError(enum.Enum):
    UNTYPED_PACKAGE = enum.auto()
    STANDALONE_MODULE = enum.auto()
    POSSIBLE_NAMESPACE_PACKAGE = enum.auto()


LibPathResult = Path | PackageError


@attrs.frozen
class PackageResolverCache:
    """Resolver / cache for packages on sys.path"""

    package_paths: Sequence[Path]
    "List of path entries to search for third party packages"
    _entries_cache: dict[Path, Mapping[str, LibPathResult]] = attrs.field(factory=dict, init=False)

    def find_package(self, pkg: str) -> LibPathResult | None:
        possible_namespace_package = False
        for lib_path in self.package_paths:
            lib_path_entries = lazy_setdefault(self._entries_cache, lib_path, self._load_lib_path)
            reason_or_path = lib_path_entries.get(pkg)
            match reason_or_path:
                case None:
                    pass
                case PackageError.UNTYPED_PACKAGE | PackageError.STANDALONE_MODULE:
                    return reason_or_path
                case PackageError.POSSIBLE_NAMESPACE_PACKAGE:
                    possible_namespace_package = True
                case path:
                    typing.assert_type(path, Path)
                    return path
        if possible_namespace_package:
            return PackageError.POSSIBLE_NAMESPACE_PACKAGE
        return None

    @staticmethod
    def _load_lib_path(lib_path: Path) -> Mapping[str, LibPathResult]:
        # ref: https://peps.python.org/pep-0420/#specification
        if not lib_path.is_dir():
            logger.debug(f"package path entry is not a directory: {lib_path}")
            return {}
        # sort entries, this will ensure directories come before python files and also
        # provide a consistent ordering
        result = dict[str, LibPathResult]()
        for dir_entry in sorted(lib_path.iterdir(), key=lambda x: x.name):
            if dir_entry.is_dir():
                name = dir_entry.name
                if dir_entry.name.isidentifier():
                    init_path = dir_entry / "__init__.py"
                    if not init_path.is_file():
                        result[name] = PackageError.POSSIBLE_NAMESPACE_PACKAGE
                    elif not (dir_entry / "py.typed").is_file():
                        result[name] = PackageError.UNTYPED_PACKAGE
                    else:
                        result[name] = init_path
            # The following files seem to determine what is a valid extension module via
            # defining _PyImport_DynLoadFiletab:
            #   - https://github.com/python/cpython/blob/3.12/Python/dynload_shlib.c
            #   - https://github.com/python/cpython/blob/3.12/Python/dynload_win.c
            #   - https://github.com/python/cpython/blob/3.12/Python/dynload_hpux.c
            # If we had easy access to the interpreter we could just use:
            #   https://docs.python.org/3/library/importlib.html#importlib.machinery.all_suffixes
            # We can't just use the current interpreter values because even though it should
            # be the correct platform it might be the wrong Python version.
            # But excluding HP-UX and cygwin, these extensions together with only looking
            # at the filename up to the first . should suffice
            elif dir_entry.is_file() and dir_entry.suffix in (".py", ".pyc", ".so", ".pyd"):
                name = dir_entry.name.partition(".")[0]
                if name in result:
                    logger.debug(f"module '{name}' is shadowed by package on path {lib_path}")
                else:
                    result[name] = PackageError.STANDALONE_MODULE
        return result


class DependencyFlags(enum.Flag):
    NONE = 0
    IMPLICIT = enum.auto()
    TYPE_CHECKING = enum.auto()
    DEFERRED = enum.auto()
    POTENTIAL_STAR_IMPORT = enum.auto()
    STUB = enum.auto()


@attrs.frozen
class Dependency:
    module_id: str
    path: Path | None
    flags: DependencyFlags
    loc: SourceLocation | None

    def __attrs_post_init__(self) -> None:
        if self.path is None:
            assert DependencyFlags.STUB in self.flags
        else:
            assert self.path == self.path.resolve()
            assert (self.path.is_dir() and not (self.path / "__init__.py").exists()) or (
                self.path.is_file() and self.path.suffixes == [".py"]
            )


def resolve_import_dependencies(
    tree: fast_nodes.Module,
    source_roots: Mapping[str, Path],
    package_cache: PackageResolverCache,
    *,
    import_base_dir: Path,
) -> list[Dependency]:
    assert all(p.is_file() and p.suffixes == [".py"] for p in source_roots.values())
    resolver = _ImportResolver(
        source_roots=source_roots,
        package_cache=package_cache,
        import_base_dir=import_base_dir,
    )
    import_dependencies = resolver.collect(tree)
    implicit_dependencies = _create_ancestor_dependencies(
        tree.name, tree.path, import_dependencies
    )
    return import_dependencies + implicit_dependencies


@attrs.define
class _ImportResolver(StatementTraverser):
    source_roots: Mapping[str, Path]
    "Source packages by their root module (either a standalone module or a pacakge __init__.py)"
    package_cache: PackageResolverCache
    import_base_dir: Path
    _flags: DependencyFlags = attrs.field(default=DependencyFlags.NONE, init=False)
    _dependencies: list[Dependency] = attrs.field(factory=list, init=False)

    def collect(self, module: fast_nodes.Module) -> list[Dependency]:
        self._dependencies.clear()
        self.visit_module(module)
        return self._dependencies.copy()

    @typing.override
    def visit_module_import(self, stmt: fast_nodes.ModuleImport) -> None:
        for imp in stmt.names:
            self._resolve_module(imp.name, imp.source_location)

    def _resolve_module(self, module_id: str, loc: SourceLocation) -> Dependency | None:
        parts = module_id.split(".")
        if "__init__" in parts:
            logger.error(
                "explicitly importing __init__.py is not supported",
                location=loc,
            )
            return None
        elif module_id in _ALLOWED_STDLIB_STUBS or parts[0] == "algopy":
            return self._add_dependency(module_id, None, loc, DependencyFlags.STUB)
        elif path := self._find_module(module_id, loc):
            return self._add_dependency(module_id, path, loc=loc)
        else:
            return None

    @typing.override
    def visit_from_import(self, from_imp: fast_nodes.FromImport) -> None:
        loc = from_imp.source_location
        primary = self._resolve_module(from_imp.module, loc)
        if primary and primary.path and primary.path.name == "__init__.py":
            # If not resolving to an init file, then a direct dependency is sufficient,
            # otherwise, we need to consider sub modules.
            module_dir = primary.path.parent
            if from_imp.names is None:
                self._resolve_from_init_import_star(from_imp.module, module_dir, loc)
            else:
                self._resolve_from_init_import_names(from_imp.module, module_dir, from_imp.names)

    def _resolve_from_init_import_names(
        self, module_id: str, module_dir: Path, names: Sequence[fast_nodes.ImportAs]
    ) -> None:
        # There are two complications at this point:
        # The first is that if x/__init__.py defines a variable foo, but there is also a
        # file x/foo.py, then `from x import foo` will actually refer to the variable.
        # This is okay, at worst we create spurious dependencies.
        # The second complication is that symbols in the __init__.py could be modules from
        # another location, this is okay because as long as there is a dependency to the
        # __init__.py file then the importer will also depend transitively on that imported
        # module. In other words, any explicit dependencies inside the __init__.py will
        # work transitively, regardless of depth.
        # References:
        # - https://docs.python.org/3/tutorial/modules.html#importing-from-a-package
        # - https://docs.python.org/3/reference/simple_stmts.html#the-import-statement

        for alias in names:
            base_path = module_dir / alias.name
            resolved_path = _resolve_module_path(base_path)
            if resolved_path is not None:
                submodule_id = ".".join((module_id, alias.name))
                # TODO: __init__.py variable shadowing could mean this is a non-existent
                #       dependency, which we would catch later under the guise of a change of type,
                #       but before that it could cause a "false" dependency cycle?
                self._add_dependency(submodule_id, resolved_path, alias.source_location)

    def _resolve_from_init_import_star(
        self, module_id: str, module_dir: Path, loc: SourceLocation
    ) -> None:
        # in the case of a star import, the dependencies are only potential dependencies,
        # in the case that init module defines an __all__ and the module is listed there
        maybe_sub_names = sorted(
            {p.stem for p in module_dir.iterdir() if (p.is_dir() or p.suffixes == [".py"])}
        )
        for maybe_sub_name in maybe_sub_names:
            base_path = module_dir / maybe_sub_name
            resolved_path = _resolve_module_path(base_path)
            if resolved_path is not None:
                submodule_id = ".".join((module_id, maybe_sub_name))
                self._add_dependency(
                    submodule_id, resolved_path, loc, DependencyFlags.POTENTIAL_STAR_IMPORT
                )

    def _add_dependency(
        self,
        module_id: str,
        path: Path | None,
        loc: SourceLocation,
        additional_flags: DependencyFlags = DependencyFlags.NONE,
    ) -> Dependency:
        result = Dependency(
            module_id=module_id, path=path, flags=self._flags | additional_flags, loc=loc
        )
        self._dependencies.append(result)
        return result

    @typing.override
    def visit_if(self, if_stmt: fast_nodes.If) -> None:
        condition = reachability.infer_condition_value(if_stmt.test)
        match condition:
            case reachability.TRUTH_VALUE_UNKNOWN:
                super().visit_if(if_stmt)
            case reachability.ALWAYS_TRUE:
                # visit only the "if" branch
                for stmt in if_stmt.body:
                    stmt.accept(self)
            case reachability.ALWAYS_FALSE:
                # visit only the "else" branch
                for stmt in if_stmt.else_body or ():
                    stmt.accept(self)
            case reachability.TYPE_CHECKING_TRUE:
                # visit the "if" branch but add TYPE_CHECKING flag
                with self._enter_scope(DependencyFlags.TYPE_CHECKING):
                    for stmt in if_stmt.body:
                        stmt.accept(self)
                # visit the "else" branch normally
                for stmt in if_stmt.else_body or ():
                    stmt.accept(self)
            case reachability.TYPE_CHECKING_FALSE:
                # visit the "if" branch normally
                for stmt in if_stmt.body:
                    stmt.accept(self)
                # visit the "else" branch but add TYPE_CHECKING flag
                with self._enter_scope(DependencyFlags.TYPE_CHECKING):
                    for stmt in if_stmt.else_body or ():
                        stmt.accept(self)
            case unexpected:
                typing.assert_never(unexpected)

    @typing.override
    def visit_function_def(self, func_def: fast_nodes.FunctionDef) -> None:
        with self._enter_scope(DependencyFlags.DEFERRED):
            super().visit_function_def(func_def)

    @contextlib.contextmanager
    def _enter_scope(self, flag: DependencyFlags) -> Iterator[None]:
        current_flags = self._flags
        self._flags |= flag
        try:
            yield
        finally:
            self._flags = current_flags

    def _find_module(self, module_id: str, import_loc: SourceLocation | None) -> Path | None:
        pkg, _sep, sub_id = module_id.partition(".")
        # pkg_result: Path
        if source_root := self.source_roots.get(pkg):
            pkg_root = source_root
        elif sys_path_result := self.package_cache.find_package(pkg):
            match sys_path_result:
                case PackageError.UNTYPED_PACKAGE:
                    logger.error(
                        f'imported module "{module_id}" comes from an untyped package,'
                        f" or a package with separate type stubs",
                        location=import_loc,
                    )
                    return None
                case PackageError.STANDALONE_MODULE:
                    logger.error(
                        f'imported module "{module_id}" comes from an standalone module',
                        location=import_loc,
                    )
                    return None
                case PackageError.POSSIBLE_NAMESPACE_PACKAGE:
                    logger.error(
                        f'imported module "{module_id}" appears to come from'
                        f" an implicit namespace package, which is not supported currently",
                        location=import_loc,
                    )
                    return None
            pkg_root = typing.assert_type(sys_path_result, Path)
        # this is a fallback for previously supported behaviour, where files co-located with
        # input sources but not part of those packages were importable
        # TODO: should this occur before package cache (ie sys.path) lookup?
        elif adjacent_result := _resolve_module_path(
            self.import_base_dir / pkg, allow_implicit_ns_dir=False
        ):
            pkg_root = adjacent_result
        else:
            logger.error(
                f'unable to resolve imported module "{module_id}": could not locate package',
                location=import_loc,
            )
            return None

        assert pkg_root.is_file() and pkg_root.suffixes == [".py"]
        if not sub_id:
            return pkg_root
        if pkg_root.name != "__init__.py":
            # we require all packages (as opposed to standalone modules), regardless of source,
            # to have an __init__.py
            maybe_module_path = None
        else:
            base_path = pkg_root.parent.joinpath(*sub_id.split("."))
            maybe_module_path = _resolve_module_path(base_path)
        if maybe_module_path is None:
            logger.error(
                f'unable to resolve imported module "{module_id}": could not locate submodule',
                location=import_loc,
            )
        return maybe_module_path


def _resolve_module_path(base_path: Path, *, allow_implicit_ns_dir: bool = True) -> Path | None:
    pkg_init_path = base_path / "__init__.py"
    standalone_module_path = base_path.with_suffix(".py")
    if pkg_init_path.is_file():
        if standalone_module_path.is_file():
            logger.error(f"{standalone_module_path} is shadowed by package {pkg_init_path}")
        return pkg_init_path
    elif standalone_module_path.is_file():
        # the directory might exist even without an __init__.py
        if base_path.is_dir():
            logger.error(
                f"{standalone_module_path} is potentially shadowed by directory {base_path}"
            )
        return standalone_module_path
    elif base_path.is_dir() and allow_implicit_ns_dir:
        return base_path
    return None


def _create_ancestor_dependencies(
    module_id: str, path: Path, import_dependencies: Sequence[Dependency]
) -> list[Dependency]:
    imports_by_name = dict[str, list[Dependency]]()
    for imp_dep in import_dependencies:
        if imp_dep.path:
            imports_by_name.setdefault(imp_dep.module_id, []).append(imp_dep)
    # create a fake entry for self, so we capture it's ancestors
    imports_by_name.setdefault(module_id, []).append(
        Dependency(module_id, path, DependencyFlags.NONE, None)
    )
    result = list[Dependency]()
    for submod_id, submod_imports in sorted(imports_by_name.items(), key=itemgetter(0)):
        (import_path,) = {imp.path for imp in submod_imports}
        assert import_path is not None, "stub imports should already be excluded"
        for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(
            submod_id, import_path
        ):
            # TODO: can we combine these (flags in particular) logically and simply?
            for submod_import in submod_imports:
                result.append(
                    Dependency(
                        ancestor_module_id,
                        ancestor_init_path,
                        submod_import.flags | DependencyFlags.IMPLICIT,
                        submod_import.loc,
                    )
                )
    return result


def _expand_init_dependencies(module_id: str, path: Path) -> Iterator[tuple[str, Path]]:
    """Check that all packages containing id have a __init__ file."""
    ancestors = list(_expand_ancestors(module_id))
    if path.name == "__init__.py":
        path = path.parent
    else:
        ancestors.pop(0)
    for ancestor in ancestors:
        path = path.parent
        init_file = path / "__init__.py"
        if init_file.is_file():
            yield ancestor, init_file


def _expand_ancestors(module_id: str) -> Iterator[str]:
    """
    Given a module_id like "a.b.c", will yield in turn: "a.b.c", "a.b", "a"
    """
    while module_id:
        yield module_id
        module_id, *_ = module_id.rpartition(".")
