import contextlib
import enum
import functools
import typing
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import attrs

from puya.parse import SourceLocation
from puyapy import reachability
from puyapy.fast import nodes as fast_nodes
from puyapy.fast.visitors.traversers import StatementTraverser
from puyapy.find_sources import ResolvedSource
from puyapy.modulefinder import FindModuleCache

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
            if imp.name in _ALLOWED_STDLIB_STUBS:
                yield Dependency(
                    imp.name,
                    path=None,
                    flags=flags | DependencyFlags.STUB,
                    loc=imp.source_location,
                )
            elif imp.name.partition(".")[0] == "algopy":
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
            else:
                path = module_resolver(imp.name, imp.source_location)
                if path is not None:
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
        if module_id in _ALLOWED_STDLIB_STUBS:
            yield Dependency(
                module_id,
                path=None,
                flags=flags | DependencyFlags.STUB,
                loc=from_imp.source_location,
            )
            continue
        if module_id.partition(".")[0] == "algopy":
            continue  # TODO: expose as dependency somehow?

        # note: there is a case that this doesn't handle, where module_id points to a directory of
        # an implicit namespace package without an __init__.py, in that case however a from-import
        # behaves differently depending on what has already been imported, which adds significant
        # complexity here - so just error altogether for now.
        path = module_resolver(module_id, from_imp.source_location)
        if path is None:
            continue

        yield Dependency(module_id, path, flags, from_imp.source_location)
        # If not resolving to an init file, then all imported symbols must be from that file.
        # Similarly, when a `from x.y import *` resolves to x/y/__init__.py, all imported symbols
        # must be from that file.
        # TODO: not true if __all__ is defined, see:
        #  https://docs.python.org/3/tutorial/modules.html#importing-from-a-package
        # also see: https://docs.python.org/3/reference/simple_stmts.html#the-import-statement
        if path.name == "__init__.py" and from_imp.names is not None:
            # There are two complications at this point:
            # The first is that if x/__init__.py defines a variable foo, but there is also a
            # file x/foo.py, then `from x import foo` will actually refer to the variable.
            # This is okay, at worst we create spurious dependencies.
            # The second complication is that symbols in the __init__.py could be modules from
            # another location, this is okay because as long as there is a dependency to the
            # __init__.py file then the importer will also depend transitively on that imported
            # module.
            mod_dir = path.parent
            for alias in from_imp.names:
                maybe_path = mod_dir / alias.name
                if maybe_path.is_dir():
                    maybe_path = maybe_path / "__init__.py"
                else:
                    maybe_path = maybe_path.with_suffix(".py")
                if maybe_path.is_file():
                    submodule_id = ".".join((module_id, alias.name))
                    yield Dependency(submodule_id, maybe_path, flags, alias.source_location)

        ancestor_flags = flags | DependencyFlags.IMPLICIT
        for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(module_id, path):
            yield Dependency(
                ancestor_module_id, ancestor_init_path, ancestor_flags, from_imp.source_location
            )


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
