import contextlib
import enum
import typing
from collections.abc import Iterator, Mapping
from pathlib import Path

import attrs

from puya import log
from puya.parse import SourceLocation
from puyapy._stub_symtables import STUB_SYMTABLES
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.visitors.traversers import StatementTraverser
from puyapy.package_path import PackageError, PackageResolverCache
from puyapy.read_source import SourceProvider

logger = log.get_logger(__name__)


class DependencyFlags(enum.Flag):
    NONE = 0
    IMPLICIT = enum.auto()
    TYPE_CHECKING = enum.auto()
    DEFERRED = enum.auto()
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
    source_provider: SourceProvider,
) -> list[Dependency]:
    assert all(p.is_file() and p.suffixes == [".py"] for p in source_roots.values())
    resolver = _ImportResolver(
        module=tree,
        source_roots=source_roots,
        package_cache=package_cache,
        import_base_dir=import_base_dir,
        source_provider=source_provider,
    )
    import_dependencies = resolver.collect()
    return import_dependencies


@attrs.define
class _ImportResolver(StatementTraverser):
    module: fast_nodes.Module
    source_roots: Mapping[str, Path]
    "Source packages by their root module (either a standalone module or a pacakge __init__.py)"
    package_cache: PackageResolverCache
    import_base_dir: Path
    source_provider: SourceProvider
    _flags: DependencyFlags = attrs.field(default=DependencyFlags.NONE, init=False)
    _dependencies: list[Dependency] = attrs.field(factory=list, init=False)

    def collect(self) -> list[Dependency]:
        self._dependencies.clear()
        self.visit_module(self.module)
        return self._dependencies.copy()

    @typing.override
    def visit_function_def(self, func_def: fast_nodes.FunctionDef) -> None:
        with self._enter_scope(DependencyFlags.DEFERRED):
            super().visit_function_def(func_def)

    @typing.override
    def visit_module_import(self, stmt: fast_nodes.ModuleImport) -> None:
        if stmt.type_checking_only:
            flags = DependencyFlags.TYPE_CHECKING
        else:
            flags = DependencyFlags.NONE
        with self._enter_scope(flags):
            for imp in stmt.names:
                self._resolve_module(imp.name, imp.source_location)

    @typing.override
    def visit_from_import(self, from_imp: fast_nodes.FromImport) -> None:
        if from_imp.type_checking_only:
            flags = DependencyFlags.TYPE_CHECKING
        else:
            flags = DependencyFlags.NONE
        with self._enter_scope(flags):
            self._process_from_import(from_imp)

    def _process_from_import(self, from_imp: fast_nodes.FromImport) -> None:
        # references
        # - https://docs.python.org/3/tutorial/modules.html#importing-from-a-package
        # - https://docs.python.org/3/reference/simple_stmts.html#the-import-statement
        if from_imp.module == self.module.name:
            # avoid creating a potentially spurious self-dependency
            if from_imp.names is None:
                logger.error(
                    "importing star from self is not supported", location=from_imp.source_location
                )
            else:
                parent_dir = self.module.path.parent
                sub_imports = {alias.name: alias.source_location for alias in from_imp.names}
                self._resolve_submodules(from_imp.module, parent_dir, sub_imports)
        else:
            resolved = self._resolve_module(from_imp.module, from_imp.source_location)
            if not resolved:
                # TODO: do we want to expand modules from stubs?
                pass
            elif resolved.is_dir():
                # in an implicit namespace dir, we don't need to consider __init__ shadowing.
                # in addition, import * doesn't import all submodules, just binds any
                # that have already been imported
                if from_imp.names is not None:
                    sub_imports = {alias.name: alias.source_location for alias in from_imp.names}
                    self._resolve_submodules(from_imp.module, resolved, sub_imports)
            # if not resolving to an init file, then a direct dependency is sufficient,
            elif resolved.name == "__init__.py":
                # variables defined in the init take precedence over submodules, so we can't
                # be certain if this is a dependency until we've determined a symbol table.
                fast = self.source_provider.parse_source(resolved, from_imp.module)
                if fast is not None:
                    module_symbols = fast.symbols.get_identifiers()
                    if from_imp.names is not None:
                        sub_imports = {
                            alias.name: alias.source_location
                            for alias in from_imp.names
                            if alias.name not in module_symbols
                        }
                        self._resolve_submodules(from_imp.module, resolved.parent, sub_imports)
                    elif fast.dunder_all is not None:
                        stmt_loc = from_imp.source_location
                        sub_imports = {
                            maybe_sub_name: stmt_loc
                            for maybe_sub_name in fast.dunder_all
                            if maybe_sub_name not in module_symbols
                        }
                        self._resolve_submodules(from_imp.module, resolved.parent, sub_imports)

    def _resolve_module(self, module_id: str, loc: SourceLocation) -> Path | None:
        if module_id == "__future__":
            logger.error("future imports are not supported", location=loc)
            return None
        elif "__init__" in module_id.split("."):
            logger.error(
                "explicitly importing __init__.py is not supported",
                location=loc,
            )
            return None
        elif module_id in STUB_SYMTABLES:
            self._add_dependency(module_id, None, loc, extra=DependencyFlags.STUB)
            return None
        elif path := self._find_module(module_id, loc):
            if not path.is_dir():
                self._add_dependency(module_id, path, loc)
            return path
        else:
            return None

    def _resolve_submodules(
        self, parent_id: str, parent_dir: Path, sub_imports: Mapping[str, SourceLocation]
    ) -> None:
        for sub_name, loc in sub_imports.items():
            submodule_id = ".".join((parent_id, sub_name))
            base_path = parent_dir / sub_name
            resolved_path = _resolve_module_path(base_path)
            if resolved_path:
                if not resolved_path.is_dir():
                    self._add_dependency(submodule_id, resolved_path, loc)
            else:
                logger.error(
                    f'unable to resolve imported module "{submodule_id}":'
                    " could not locate submodule",
                    location=loc,
                )

    def _add_dependency(
        self,
        module_id: str,
        path: Path | None,
        loc: SourceLocation,
        *,
        extra: DependencyFlags = DependencyFlags.NONE,
    ) -> Dependency:
        result = Dependency(module_id=module_id, path=path, flags=self._flags | extra, loc=loc)
        self._dependencies.append(result)
        return result

    @contextlib.contextmanager
    def _enter_scope(self, flag: DependencyFlags) -> Iterator[None]:
        current_flags = self._flags
        self._flags |= flag
        try:
            yield
        finally:
            self._flags = current_flags

    def _find_module(self, module_id: str, import_loc: SourceLocation | None) -> Path | None:
        pkg, *rest = module_id.split(".")
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
                        f'imported module "{module_id}" comes from a standalone module',
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
        if not rest:
            return pkg_root
        # we require all packages (as opposed to standalone modules), regardless of source,
        # to have an __init__.py
        if pkg_root.name == "__init__.py":
            base_path = pkg_root.parent.joinpath(*rest)
            maybe_module_path = _resolve_module_path(base_path)
            if maybe_module_path:
                return maybe_module_path
        logger.error(
            f'unable to resolve imported module "{module_id}": could not locate submodule',
            location=import_loc,
        )
        return None


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
    elif allow_implicit_ns_dir and base_path.is_dir():
        return base_path
    return None
