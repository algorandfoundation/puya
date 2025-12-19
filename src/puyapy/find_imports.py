import contextlib
import typing
from collections.abc import Iterator, Mapping
from pathlib import Path

import attrs

from puya import log
from puya.parse import SourceLocation
from puyapy._stub_symtables import STUB_SYMTABLES
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.visitors.traversers import StatementTraverser
from puyapy.find_sources import ResolvedSource
from puyapy.package_path import PackageError, PackageResolverCache
from puyapy.read_source import SourceProvider

logger = log.get_logger(__name__)


# class DependencyFlags(enum.Flag):
#     NONE = 0
#     IMPLICIT = enum.auto()
#     TYPE_CHECKING = enum.auto()
#     DEFERRED = enum.auto()
#     STUB = enum.auto()
#     DEFINED_IN_INIT = enum.auto()


@attrs.frozen
class ResolvedImport:
    module_id: str
    path: Path

    def __attrs_post_init__(self) -> None:
        assert self.path == self.path.resolve()
        assert _is_python_file(self.path)


def _is_python_file(path: Path) -> bool:
    return path.is_file() and path.suffixes == [".py"]


@attrs.define
class ImportResolver(StatementTraverser):
    module: fast_nodes.Module
    source_roots: Mapping[str, Path]
    "Source packages by their root module (either a standalone module or a pacakge __init__.py)"
    package_cache: PackageResolverCache
    import_base_dir: Path
    source_provider: SourceProvider
    result: list[ResolvedImport] = attrs.field(factory=list, init=False)
    _is_top_level: bool = attrs.field(default=True, init=False)

    @classmethod
    def collect(
        cls,
        module: fast_nodes.Module,
        source_roots: Mapping[str, Path],
        package_cache: PackageResolverCache,
        *,
        import_base_dir: Path,
        source_provider: SourceProvider,
    ) -> list[ResolvedSource]:
        assert all(_is_python_file(p) for p in source_roots.values())
        resolver = cls(
            module=module,
            source_roots=source_roots,
            package_cache=package_cache,
            import_base_dir=import_base_dir,
            source_provider=source_provider,
        )
        resolver.visit_module(module)
        return [
            ResolvedSource(ri.path, ri.module_id, base_dir=_infer_base_dir(ri.path, ri.module_id))
            for ri in resolver.result
        ]

    @typing.override
    def visit_module(self, module: fast_nodes.Module) -> None:
        with self._enter_block(top_level=True):
            super().visit_module(module)

    @typing.override
    def visit_function_def(self, node: fast_nodes.FunctionDef) -> None:
        with self._enter_block(top_level=True):
            super().visit_function_def(node)

    @typing.override
    def visit_class_def(self, node: fast_nodes.ClassDef) -> None:
        with self._enter_block(top_level=True):
            super().visit_class_def(node)

    @typing.override
    def visit_for(self, node: fast_nodes.For) -> None:
        with self._enter_block(top_level=False):
            super().visit_for(node)

    @typing.override
    def visit_while(self, node: fast_nodes.While) -> None:
        with self._enter_block(top_level=False):
            super().visit_while(node)

    @typing.override
    def visit_if(self, node: fast_nodes.If) -> None:
        with self._enter_block(top_level=False):
            super().visit_if(node)

    @typing.override
    def visit_match(self, node: fast_nodes.Match) -> None:
        with self._enter_block(top_level=False):
            super().visit_match(node)

    @contextlib.contextmanager
    def _enter_block(self, *, top_level: bool) -> Iterator[None]:
        was_top_level = self._is_top_level
        self._is_top_level = top_level
        try:
            yield
        finally:
            self._is_top_level = was_top_level

    @typing.override
    def visit_module_import(self, stmt: fast_nodes.ModuleImport) -> None:
        if self._require_top_level(stmt):
            for imp in stmt.names:
                module_id = imp.name
                resolved = self._resolve_module(module_id, imp.source_location)
                if resolved and not resolved.is_dir():
                    self.result.append(ResolvedImport(module_id=module_id, path=resolved))

    @typing.override
    def visit_from_import(self, from_import: fast_nodes.FromImport) -> None:
        if self._require_top_level(from_import):
            self._process_from_import(from_import)

    def _require_top_level(self, stmt: fast_nodes.AnyImport) -> bool:
        if not self._is_top_level:
            logger.error(
                "import statements cannot be nested inside control structures,"
                " except for TYPE_CHECKING conditions which are allowed at the module level",
                location=stmt.source_location,
            )
        return self._is_top_level

    def _resolve_module(self, module_id: str, import_loc: SourceLocation | None) -> Path | None:
        if module_id == "__future__":
            logger.error("future imports are not supported", location=import_loc)
            return None

        parts = module_id.split(".")
        if parts[-1] == "__init__":
            logger.error("explicitly importing __init__.py is not supported", location=import_loc)
            return None

        if module_id in STUB_SYMTABLES:
            return None

        pkg, *rest = parts
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

    def _process_from_import(self, from_imp: fast_nodes.FromImport) -> None:
        # references
        # - https://docs.python.org/3/tutorial/modules.html#importing-from-a-package
        # - https://docs.python.org/3/reference/simple_stmts.html#the-import-statement
        resolved = self._resolve_module(from_imp.module, from_imp.source_location)
        if not resolved:
            pass
        elif resolved == self.module.path:
            # avoid creating a potentially spurious self-dependency
            if from_imp.names is None:
                logger.error(
                    "importing star from self is not supported", location=from_imp.source_location
                )
            elif resolved.name != "__init__.py":
                logger.error(
                    "attempted to import from the current module, but module is not a package",
                    location=from_imp.source_location,
                )
            else:
                # don't ever treat self-imports in an __init__.py as potentially being non-modules,
                # even if that's theoretically possible
                sub_imports = {alias.name: alias.source_location for alias in from_imp.names}
                self._resolve_submodules(
                    from_imp.module, resolved.parent, sub_imports, might_be_var=False
                )
        elif resolved.is_dir():
            # in an implicit namespace dir, we don't need to consider __init__ shadowing.
            # in addition, import * doesn't import all submodules, just binds any
            # that have already been imported
            if from_imp.names is not None:
                sub_imports = {alias.name: alias.source_location for alias in from_imp.names}
                self._resolve_submodules(
                    from_imp.module, resolved, sub_imports, might_be_var=False
                )
        else:
            self.result.append(ResolvedImport(from_imp.module, resolved))
            if resolved.name == "__init__.py":
                if from_imp.names is not None:
                    sub_imports = {alias.name: alias.source_location for alias in from_imp.names}
                else:
                    # `from pkg import *` will only import modules:
                    #  1) declared in pkg/__init__.py:__all__ OR
                    #  2) imported in pkg/__init__.py - don't need to worry about those,
                    #     they'll be discovered during processing on pkg/__init__.py itself.
                    fast = self.source_provider.parse_source(resolved, from_imp.module)
                    if fast and fast.dunder_all:
                        sub_imports = {
                            maybe_sub_name: from_imp.source_location
                            for maybe_sub_name in fast.dunder_all
                        }
                    else:
                        sub_imports = None
                if sub_imports:
                    self._resolve_submodules(
                        from_imp.module, resolved.parent, sub_imports, might_be_var=True
                    )

    def _resolve_submodules(
        self,
        parent_id: str,
        parent_dir: Path,
        sub_imports: Mapping[str, SourceLocation],
        *,
        might_be_var: bool,
    ) -> None:
        for sub_name, loc in sub_imports.items():
            submodule_id = ".".join((parent_id, sub_name))
            base_path = parent_dir / sub_name
            submodule_path = _resolve_module_path(base_path)
            if submodule_path:
                if not submodule_path.is_dir():
                    self.result.append(ResolvedImport(submodule_id, submodule_path))
            elif not might_be_var:
                logger.error(
                    f'unable to resolve imported module "{submodule_id}":'
                    " could not locate submodule",
                    location=loc,
                )


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


def _infer_base_dir(path: Path, module: str) -> Path:
    # /a/pkg/foo.py, pkg.foo -> /a/
    # /a/pkg/foo/__init__.py, pkg.foo -> /a/
    # /a/foo.py, foo -> /a/
    parts = module.count(".")
    if path.name == "__init__.py":
        parts += 1
    return path.parents[parts]
