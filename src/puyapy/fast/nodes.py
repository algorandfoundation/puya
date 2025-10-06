import abc
from pathlib import Path

import attrs

from puya.parse import SourceLocation
from puyapy.fast.visitors import StatementVisitor


@attrs.frozen
class Node:
    source_location: SourceLocation


@attrs.frozen
class Statement(Node, abc.ABC):
    @abc.abstractmethod
    def accept[T](self, visitor: StatementVisitor[T]) -> T: ...


@attrs.frozen
class ImportAs(Node):
    name: str
    as_name: str | None


@attrs.frozen
class ModuleImport(Statement):
    names: list[ImportAs] = attrs.field(validator=attrs.validators.min_len(1))

    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_module_import(self)


@attrs.frozen
class FromImport(Statement):
    module: str
    names: list[ImportAs] | None = attrs.field(
        validator=attrs.validators.optional(attrs.validators.min_len(1))
    )
    """if None, then import all (ie star import)"""

    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_from_import(self)


AnyImport = ModuleImport | FromImport


@attrs.frozen
class Parameter(Node):
    name: str
    annotation: str


@attrs.frozen
class FunctionDef(Statement):
    name: str
    parameters: tuple[Parameter, ...]

    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_function_def(self)


@attrs.frozen
class Module:
    name: str
    path: Path
    body: tuple[Statement, ...]
