import ast
import contextlib
import enum
import symtable
import typing
from collections.abc import Iterator, Mapping, Set
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
    _symbol_tables_cache: dict[Path, Set[str] | None] = attrs.field(factory=dict, init=False)

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

        loc = from_imp.source_location
        if from_imp.module == self.module.name:
            # avoid creating a potentially spurious self-dependency
            if from_imp.names is None:
                logger.error("cannot import star from self", location=from_imp.source_location)
            else:
                parent_dir = self.module.path.parent
                for alias in from_imp.names:
                    base_path = parent_dir / alias.name
                    resolved_path = _resolve_module_path(base_path, allow_implicit_ns_dir=False)
                    if resolved_path is not None:
                        submodule_id = ".".join((from_imp.module, alias.name))
                        self._add_dependency(submodule_id, resolved_path, loc)
            return
        maybe_resolved = self._resolve_module(from_imp.module, loc)
        if maybe_resolved is None:
            # TODO: do we want to expand modules from stubs?
            return
        resolved = maybe_resolved
        if resolved.is_dir():
            # in an implicit namespace dir, we don't need to consider __init__ shadowing.
            # in addition, import * doesn't import all submodules, just binds any
            # that have already been imported
            for alias in from_imp.names or ():
                submodule_id = ".".join((from_imp.module, alias.name))
                self._resolve_module(submodule_id, alias.source_location)
        # if not resolving to an init file, then a direct dependency is sufficient,
        elif resolved.name == "__init__.py":
            # variables defined in the init take precedence over submodules, so we can't
            # be certain if this is a dependency until we've determined a symbol table.
            module_symbols = self._read_symbol_table(resolved)
            if module_symbols is not None:
                if from_imp.names is not None:
                    maybe_sub_names = [
                        (alias.name, alias.source_location) for alias in from_imp.names
                    ]
                else:
                    maybe_sub_names = []
                    if "__all__" in module_symbols:
                        dunder_all = self._read_dunder_all(resolved)
                        if dunder_all is None:
                            logger.error(
                                f"unable to determine __all__ value for module {from_imp.module}",
                                location=loc,
                            )
                        else:
                            maybe_sub_names = [
                                (maybe_sub_name, loc) for maybe_sub_name in dunder_all
                            ]
                module_dir = resolved.parent
                for maybe_sub_name, loc in maybe_sub_names:
                    if maybe_sub_name not in module_symbols:
                        base_path = module_dir / maybe_sub_name
                        resolved_path = _resolve_module_path(
                            base_path, allow_implicit_ns_dir=False
                        )
                        if resolved_path is not None:
                            submodule_id = ".".join((from_imp.module, maybe_sub_name))
                            self._add_dependency(submodule_id, resolved_path, loc)

    def _read_symbol_table(self, path: Path) -> Set[str] | None:
        try:
            return self._symbol_tables_cache[path]
        except KeyError:
            pass
        try:
            source = self.source_provider.read_source(path)
            st = symtable.symtable(source, str(path), "exec")
        except Exception as ex:
            logger.debug(ex)
            module_symbols = None
        else:
            module_symbols = st.get_identifiers()
        self._symbol_tables_cache[path] = module_symbols
        return module_symbols

    def _read_dunder_all(self, path: Path) -> list[str] | None:
        source = self.source_provider.read_source(path)
        mod = ast.parse(source, path)
        dunder_all: list[str] | None = None
        # TODO: make this more robust, maybe use FAST instead, could cache the result
        for ast_stmt in mod.body:
            if isinstance(ast_stmt, ast.Assign):
                if _is_dunder_all_assignment_target(ast_stmt.targets):
                    dunder_all = _extract_literal_str_list(ast_stmt.value)
            elif dunder_all is not None and isinstance(ast_stmt, ast.AugAssign):  # noqa: SIM102
                if isinstance(ast_stmt.op, ast.Add) and _is_dunder_all_assignment_target(
                    [ast_stmt.target]
                ):
                    dunder_all += _extract_literal_str_list(ast_stmt.value)
        return dunder_all

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


def _is_dunder_all_assignment_target(targets: list[ast.expr]) -> bool:
    match targets:
        case [ast.Name(id="__all__")]:
            return True
        case _:
            return False


def _extract_literal_str_list(value: ast.expr) -> list[str]:
    result = []
    match value:
        case ast.List(elts=elements) | ast.Tuple(elts=elements):
            for el in elements:
                match el:
                    case ast.Constant(value=str(name)):
                        result.append(name)
    return result
