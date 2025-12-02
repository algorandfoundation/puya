import contextlib
import enum
import functools
import typing
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.parse import SourceLocation
from puyapy import reachability
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.visitors.traversers import StatementTraverser
from puyapy.find_sources import ResolvedSource
from puyapy.modulefinder import FindModuleCache

logger = log.get_logger(__name__)

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


def resolve_import_dependencies(
    source: ResolvedSource,
    tree: fast_nodes.Module,
    fmc: FindModuleCache,
) -> list[Dependency]:
    visitor = _ImportCollector()
    visitor.visit_module(tree)
    module_imports = visitor.module_imports
    from_imports = visitor.from_imports

    import_base_dir = source.base_dir or source.path.parent
    module_resolver = functools.partial(fmc.find_module, import_base_dir=import_base_dir)
    dependencies = list(_resolve_module_import_dependencies(module_imports, module_resolver))
    dependencies.extend(_resolve_from_imports_dependencies(from_imports, module_resolver))
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
    module_resolver: Callable[[str, SourceLocation | None], Path | None],
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
            elif path := module_resolver(imp.name, imp.source_location):
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
    module_resolver: Callable[[str, SourceLocation | None], Path | None],
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
        elif path := module_resolver(module_id, from_imp.source_location):
            yield Dependency(module_id, path, flags, from_imp.source_location)
            # If not resolving to an init file, then a direct dependency is sufficient,
            # otherwise, we need to consider sub modules.
            if path.name == "__init__.py":
                yield from _resolve_from_init_import_submodules(from_imp, path, flags)

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
    from_imp: fast_nodes.FromImport, path: Path, flags: DependencyFlags
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
            sub_pkg_init_path = mod_dir / alias.name / "__init__.py"
            standalone_module_path = mod_dir / f"{alias.name}.py"
            maybe_path = None
            if sub_pkg_init_path.is_file():
                if standalone_module_path.is_file():
                    logger.error(
                        f"{standalone_module_path} is shadowed by package {sub_pkg_init_path}"
                    )
                maybe_path = sub_pkg_init_path
            elif standalone_module_path.is_file():
                maybe_path = standalone_module_path
            if maybe_path is not None:
                submodule_id = ".".join((module_id, alias.name))
                yield Dependency(submodule_id, maybe_path, flags, alias.source_location)
    else:
        # in the case of a star import, the dependencies are only potential dependencies,
        # in the case that init module defines an __all__ and the module is listed there
        flags |= DependencyFlags.POTENTIAL_STAR_IMPORT
        seen_sub_names = set[str]()
        for sub_pkg_init_path in sorted(mod_dir.glob("*/__init__.py")):
            sub_name = sub_pkg_init_path.parent.name
            seen_sub_names.add(sub_name)
            submodule_id = ".".join((module_id, sub_name))
            yield Dependency(submodule_id, sub_pkg_init_path, flags, from_imp.source_location)
        for sub_mod_path in sorted(mod_dir.glob("*.py")):
            sub_name = sub_mod_path.stem
            if sub_mod_path != path and sub_name not in seen_sub_names:
                submodule_id = ".".join((module_id, sub_name))
                yield Dependency(submodule_id, sub_mod_path, flags, from_imp.source_location)


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
