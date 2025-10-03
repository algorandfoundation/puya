import ast
import typing
from collections.abc import Iterator
from pathlib import Path

import attrs

from puya.errors import CodeError
from puya.parse import SourceLocation
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


@attrs.frozen
class ImportAs:
    loc: SourceLocation
    name: str
    as_name: str | None


@attrs.frozen
class ModuleImport:
    loc: SourceLocation
    names: list[ImportAs] = attrs.field(validator=attrs.validators.min_len(1))


@attrs.frozen
class FromImport:
    loc: SourceLocation
    module: str
    names: list[ImportAs] | None = attrs.field(
        validator=attrs.validators.optional(attrs.validators.min_len(1))
    )
    """if None, then import all (ie star import)"""


AnyImport = ModuleImport | FromImport


@attrs.define
class _ImportCollector(ast.NodeVisitor):
    source: ResolvedSource
    module_imports: list[ModuleImport] = attrs.field(factory=list, init=False)
    from_imports: list[FromImport] = attrs.field(factory=list, init=False)

    @typing.override
    def visit_Import(self, node: ast.Import) -> None:
        names = [
            ImportAs(
                name=alias.name,
                as_name=alias.asname,
                loc=self._loc(alias),
            )
            for alias in node.names
        ]
        self.module_imports.append(
            ModuleImport(
                names=names,
                loc=self._loc(node),
            )
        )

    @typing.override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        match node.names:
            case [ast.alias("*", None)]:
                names = None
            case _:
                names = list[ImportAs](
                    ImportAs(
                        name=alias.name,
                        as_name=alias.asname,
                        loc=self._loc(alias),
                    )
                    for alias in node.names
                )

        node_loc = self._loc(node)
        if not node.level:
            assert node.module
            module = node.module
        else:
            module = self._correct_relative_import(
                module=node.module, level=node.level, loc=node_loc
            )

        self.from_imports.append(
            FromImport(
                module=module,
                names=names,
                loc=node_loc,
            )
        )

    def _loc(self, node: ast.expr | ast.stmt | ast.alias) -> SourceLocation:
        return _ast_source_location(node, self.source.path)

    def _correct_relative_import(self, module: str | None, level: int, loc: SourceLocation) -> str:
        """Function to correct for relative imports."""
        file_id = self.source.module
        rel = level
        assert level > 0
        if self.source.path.stem == "__init__":
            rel -= 1
        if rel != 0:
            file_id = ".".join(file_id.split(".")[:-rel])

        if module:
            new_id = file_id + "." + module
        else:
            new_id = file_id

        if not new_id:
            # TODO: log and exit at end of discovery
            raise CodeError("no parent module, cannot perform relative import", loc)

        return new_id


def _ast_source_location(node: ast.expr | ast.stmt | ast.alias, file: Path) -> SourceLocation:
    return SourceLocation(file=file, line=node.lineno)


@attrs.frozen
class Dependency:
    module_id: str
    path: Path
    loc: SourceLocation | None
    implicit: bool


def resolve_import_dependencies(
    source: ResolvedSource,
    tree: ast.Module,
    fmc: FindModuleCache,
) -> list[Dependency]:
    visitor = _ImportCollector(source)
    visitor.visit(tree)

    dependencies = []
    import_base_dir = source.base_dir or source.path.parent
    for mod_imp in visitor.module_imports:
        for alias in mod_imp.names:
            if alias.name in _ALLOWED_STDLIB_STUBS:
                continue
            if alias.name.partition(".")[0] == "algopy":
                continue
            path_str = fmc.find_module(alias.name, alias.loc, import_base_dir=import_base_dir)
            if path_str is None:
                continue

            path = Path(path_str)
            dependencies.append(Dependency(alias.name, path, alias.loc, implicit=False))
            for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(
                alias.name, path
            ):
                dependencies.append(
                    Dependency(ancestor_module_id, ancestor_init_path, alias.loc, implicit=True)
                )
    for from_imp in visitor.from_imports:
        module_id = from_imp.module
        if module_id in _ALLOWED_STDLIB_STUBS:
            continue
        if module_id.partition(".")[0] == "algopy":
            continue

        # note: there is a case that this doesn't handle, where module_id points to a directory of
        # an implicit namespace package without an __init__.py, in that case however a from-import
        # behaves differently depending on what has already been imported, which adds significant
        # complexity here - so just error altogether for now.
        path_str = fmc.find_module(module_id, from_imp.loc, import_base_dir=import_base_dir)
        if path_str is None:
            continue

        path = Path(path_str)
        sub_deps = []
        any_unresolved = False
        # If not resolving to an init file, then all imported symbols must be from that file.
        # Similarly, when a `from x.y import *` resolves to x/y/__init__.py, all imported symbols
        # must be from that file.
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
                    sub_deps.append(
                        Dependency(submodule_id, maybe_path, alias.loc, implicit=False)
                    )
                else:
                    any_unresolved = True
        dependencies.append(Dependency(module_id, path, from_imp.loc, implicit=not any_unresolved))
        dependencies.extend(sub_deps)
        for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(module_id, path):
            dependencies.append(
                Dependency(ancestor_module_id, ancestor_init_path, from_imp.loc, implicit=True)
            )

    for ancestor_module_id, ancestor_init_path in _expand_init_dependencies(
        source.module, source.path
    ):
        dependencies.append(
            Dependency(ancestor_module_id, ancestor_init_path, None, implicit=True)
        )
    return dependencies


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
