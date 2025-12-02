import contextlib
import enum
import typing
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault
from puyapy import reachability
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.visitors.traversers import StatementTraverser
from puyapy.find_sources import ResolvedSource

logger = log.get_logger(__name__)


@enum.unique
class ModuleNotFoundReason(enum.Enum):
    PACKAGE_NOT_FOUND = enum.auto()
    SUBMODULE_NOT_FOUND = enum.auto()
    UNTYPED_PACKAGE = enum.auto()
    STANDALONE_MODULE = enum.auto()
    POSSIBLE_NAMESPACE_PACKAGE = enum.auto()


ModuleSearchResult = Path | ModuleNotFoundReason
LibPathResult = (
    Path
    | typing.Literal[
        ModuleNotFoundReason.UNTYPED_PACKAGE,
        ModuleNotFoundReason.STANDALONE_MODULE,
        ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE,
    ]
)

_LibPath = Sequence[Path]

_ALLOWED_STDLIB_STUBS: typing.Final = frozenset(
    (
        "abc",
        "typing",
        # not technically stlib, but treated as synonym for typing for our purposes
        "typing_extensions",
    )
)


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


@attrs.frozen(kw_only=True)
class FindModuleCache:
    package_roots: Mapping[str, Path]
    "Known packages and their root module (either a standalone module or a pacakge __init__.py)"
    package_paths: _LibPath
    "List of path entries to search for third party packages"
    _results: dict[str, ModuleSearchResult] = attrs.field(factory=dict, init=False)
    _lib_path_cache: dict[Path, Mapping[str, LibPathResult]] = attrs.field(
        factory=dict, init=False
    )

    def __attrs_post_init__(self) -> None:
        assert all(p.is_file() and p.suffixes == [".py"] for p in self.package_roots.values())

    def find_module(
        self, module_id: str, import_loc: SourceLocation | None, import_base_dir: Path
    ) -> Path | None:
        path_or_reason = self.try_find_module(module_id, import_base_dir)
        match path_or_reason:
            case ModuleNotFoundReason.PACKAGE_NOT_FOUND:
                logger.error(
                    f'unable to resolve imported module "{module_id}": could not locate package',
                    location=import_loc,
                )
                return None
            case ModuleNotFoundReason.SUBMODULE_NOT_FOUND:
                logger.error(
                    f'unable to resolve imported module "{module_id}": could not locate submodule',
                    location=import_loc,
                )
                return None
            case ModuleNotFoundReason.UNTYPED_PACKAGE:
                logger.error(
                    f'imported module "{module_id}" comes from an untyped package,'
                    f" or a package with separate type stubs",
                    location=import_loc,
                )
                return None
            case ModuleNotFoundReason.STANDALONE_MODULE:
                logger.error(
                    f'imported module "{module_id}" comes from an standalone module',
                    location=import_loc,
                )
                return None
            case ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE:
                logger.error(
                    f'imported module "{module_id}" appears to come from'
                    f" an implicit namespace package, which is not supported currently",
                    location=import_loc,
                )
                return None
            case path:
                return path

    def try_find_module(self, module_id: str, import_base_dir: Path) -> ModuleSearchResult:
        result = lazy_setdefault(self._results, module_id, self._find_module)
        # this is a fallback for previously supported behaviour, where files co-located with
        # input sources but not part of those packages were importable
        if result is ModuleNotFoundReason.PACKAGE_NOT_FOUND:
            pkg, _sep, sub_id = module_id.partition(".")
            pkg_init_path = import_base_dir / pkg / "__init__.py"
            standalone_module_path = (import_base_dir / pkg).with_suffix(".py")
            pkg_root = None
            if pkg_init_path.is_file():
                if standalone_module_path.is_file():
                    logger.error(
                        f"{standalone_module_path} is shadowed by package {pkg_init_path}"
                    )
                pkg_root = pkg_init_path
            elif standalone_module_path.is_file():
                pkg_root = standalone_module_path
            if pkg_root is not None:
                return self._find_submodule(pkg_root, sub_id)
        return result

    def _find_module(self, module_id: str) -> ModuleSearchResult:
        pkg, _sep, sub_id = module_id.partition(".")
        if pkg_root := self.package_roots.get(pkg):
            return self._find_submodule(pkg_root, sub_id)
        possible_namespace_package = False
        for lib_path in self.package_paths:
            lib_path_entries = lazy_setdefault(self._lib_path_cache, lib_path, self._load_lib_path)
            reason_or_path = lib_path_entries.get(pkg)
            match reason_or_path:
                case None:
                    pass
                case ModuleNotFoundReason.UNTYPED_PACKAGE | ModuleNotFoundReason.STANDALONE_MODULE:
                    return reason_or_path
                case ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE:
                    possible_namespace_package = True
                case path:
                    typing.assert_type(path, Path)
                    return self._find_submodule(path, sub_id)
        if possible_namespace_package:
            return ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE
        return ModuleNotFoundReason.PACKAGE_NOT_FOUND

    @staticmethod
    def _find_submodule(pkg_root: Path, sub_id: str) -> ModuleSearchResult:
        assert pkg_root.is_file() and pkg_root.suffixes == [".py"]
        if not sub_id:
            return pkg_root
        if pkg_root.name != "__init__.py":
            return ModuleNotFoundReason.SUBMODULE_NOT_FOUND
        mod_path = pkg_root.parent.joinpath(*sub_id.split("."))
        if mod_path.is_dir():
            mod_init_path = mod_path / "__init__.py"
            if mod_init_path.is_file():
                return mod_init_path
            else:
                return mod_path
        else:
            mod_path = mod_path.with_suffix(".py")
            if mod_path.is_file():
                return mod_path
            else:
                return ModuleNotFoundReason.SUBMODULE_NOT_FOUND

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
                        result[name] = ModuleNotFoundReason.POSSIBLE_NAMESPACE_PACKAGE
                    elif not (dir_entry / "py.typed").is_file():
                        result[name] = ModuleNotFoundReason.UNTYPED_PACKAGE
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
                    result[name] = ModuleNotFoundReason.STANDALONE_MODULE
        return result


class ImportDependencyResolver:
    def __init__(self, package_roots: Mapping[str, Path], package_paths: _LibPath):
        self._fmc = FindModuleCache(package_roots=package_roots, package_paths=package_paths)

    def resolve_import_dependencies(
        self, source: ResolvedSource, tree: fast_nodes.Module
    ) -> list[Dependency]:
        visitor = _ImportCollector()
        visitor.visit_module(tree)
        module_imports = visitor.module_imports
        from_imports = visitor.from_imports

        import_base_dir = source.base_dir or source.path.parent
        dependencies = list(
            _resolve_module_import_dependencies(module_imports, self._fmc, import_base_dir)
        )
        dependencies.extend(
            _resolve_from_imports_dependencies(from_imports, self._fmc, import_base_dir)
        )
        dependencies.extend(
            Dependency(ancestor_module_id, ancestor_init_path, DependencyFlags.IMPLICIT, loc=None)
            for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(
                source.module, source.path
            )
        )
        return dependencies


@attrs.define
class _ImportCollector(StatementTraverser):
    module_imports: list[tuple[fast_nodes.ModuleImport, DependencyFlags]] = attrs.field(
        factory=list, init=False
    )
    from_imports: list[tuple[fast_nodes.FromImport, DependencyFlags]] = attrs.field(
        factory=list, init=False
    )
    _flags: DependencyFlags = attrs.field(default=DependencyFlags.NONE, init=False)

    @typing.override
    def visit_module_import(self, module_import: fast_nodes.ModuleImport) -> None:
        self.module_imports.append((module_import, self._flags))

    @typing.override
    def visit_from_import(self, from_import: fast_nodes.FromImport) -> None:
        self.from_imports.append((from_import, self._flags))

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


def _resolve_module_import_dependencies(
    module_imports: Sequence[tuple[fast_nodes.ModuleImport, DependencyFlags]],
    fmc: FindModuleCache,
    import_base_dir: Path,
) -> Iterator[Dependency]:
    for stmt, flags in module_imports:
        for imp in stmt.names:
            parts = imp.name.split(".")
            if "__init__" in parts:
                logger.error(
                    "explicitly importing __init__.py is not supported",
                    location=imp.source_location,
                )
            elif imp.name in _ALLOWED_STDLIB_STUBS:
                yield Dependency(
                    imp.name,
                    path=None,
                    flags=flags | DependencyFlags.STUB,
                    loc=imp.source_location,
                )
            elif parts[0] == "algopy":
                for module_id in _expand_ancestors(imp.name):
                    yield Dependency(
                        module_id,
                        path=None,
                        flags=(
                            (flags | DependencyFlags.STUB)
                            if module_id == imp.name
                            else (flags | DependencyFlags.STUB | DependencyFlags.IMPLICIT)
                        ),
                        loc=imp.source_location,
                    )
            elif path := fmc.find_module(imp.name, imp.source_location, import_base_dir):
                yield Dependency(imp.name, path, flags, imp.source_location)
                ancestor_flags = flags | DependencyFlags.IMPLICIT
                for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(
                    imp.name, path
                ):
                    yield Dependency(
                        ancestor_module_id,
                        ancestor_init_path,
                        ancestor_flags,
                        imp.source_location,
                    )


def _resolve_from_imports_dependencies(
    from_imports: Sequence[tuple[fast_nodes.FromImport, DependencyFlags]],
    fmc: FindModuleCache,
    import_base_dir: Path,
) -> Iterator[Dependency]:
    for from_imp, flags in from_imports:
        module_id = from_imp.module
        parts = module_id.split(".")
        if "__init__" in parts:
            logger.error(
                "explicitly importing __init__.py is not supported",
                location=from_imp.source_location,
            )
        elif module_id in _ALLOWED_STDLIB_STUBS:
            yield Dependency(
                module_id,
                path=None,
                flags=flags | DependencyFlags.STUB,
                loc=from_imp.source_location,
            )
        elif parts[0] == "algopy":
            continue  # TODO: expose as dependency
        elif path := fmc.find_module(module_id, from_imp.source_location, import_base_dir):
            yield Dependency(module_id, path, flags, from_imp.source_location)
            # If not resolving to an init file, then a direct dependency is sufficient,
            # otherwise, we need to consider sub modules.
            if path.name == "__init__.py":
                yield from _resolve_from_init_import_submodules(
                    from_imp, path, flags, fmc, import_base_dir
                )

            ancestor_flags = flags | DependencyFlags.IMPLICIT
            for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(
                module_id, path
            ):
                yield Dependency(
                    ancestor_module_id,
                    ancestor_init_path,
                    ancestor_flags,
                    from_imp.source_location,
                )


def _resolve_from_init_import_submodules(
    from_imp: fast_nodes.FromImport,
    path: Path,
    flags: DependencyFlags,
    fmc: FindModuleCache,
    import_base_dir: Path,
) -> Iterator[Dependency]:
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

    module_id = from_imp.module
    mod_dir = path.parent
    if from_imp.names is not None:
        for alias in from_imp.names:
            submodule_id = ".".join((module_id, alias.name))
            maybe_path = fmc.try_find_module(submodule_id, import_base_dir)
            if isinstance(maybe_path, Path):
                yield Dependency(submodule_id, maybe_path, flags, alias.source_location)
    else:
        # in the case of a star import, the dependencies are only potential dependencies,
        # in the case that init module defines an __all__ and the module is listed there
        flags |= DependencyFlags.POTENTIAL_STAR_IMPORT
        maybe_sub_names = sorted(
            {p.stem for p in mod_dir.iterdir() if (p.is_dir() or p.suffixes == [".py"])}
        )
        for maybe_sub_name in maybe_sub_names:
            submodule_id = ".".join((module_id, maybe_sub_name))
            maybe_path = fmc.try_find_module(submodule_id, import_base_dir)
            if isinstance(maybe_path, Path):
                yield Dependency(submodule_id, maybe_path, flags, from_imp.source_location)


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
