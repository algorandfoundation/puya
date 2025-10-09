import abc
import ast
import types
import typing
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya.parse import SourceLocation
from puyapy.fast.visitors import ExpressionVisitor, StatementVisitor


@attrs.frozen
class Node(abc.ABC):
    source_location: SourceLocation


@attrs.frozen
class Statement(Node, abc.ABC):
    @abc.abstractmethod
    def accept[T](self, visitor: StatementVisitor[T]) -> T: ...


@attrs.frozen
class Expression(Node, abc.ABC):
    @abc.abstractmethod
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T: ...


@attrs.frozen
class ImportAs(Node):
    name: str
    as_name: str | None


@attrs.frozen
class ModuleImport(Statement):
    names: list[ImportAs] = attrs.field(validator=attrs.validators.min_len(1))

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_module_import(self)


@attrs.frozen
class FromImport(Statement):
    module: str
    names: list[ImportAs] | None = attrs.field(
        validator=attrs.validators.optional(attrs.validators.min_len(1))
    )
    """if None, then import all (ie star import)"""

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_from_import(self)


AnyImport = ModuleImport | FromImport


@attrs.frozen
class Parameter(Node):
    name: str
    annotation: Expression | None


@attrs.frozen
class Decorator(Node):
    # Technically, as of Python 3.9, decorators can be almost any arbitrary expression,
    # however there's no such decorator that we support or could envision supporting,
    # so keep things simple and only translate dotted-expressions followed by at most one
    # function argument list.
    # ref: https://peps.python.org/pep-0614/
    callee: str
    # we do allow som extra syntax in certain decorator arguments however, so retain
    # the original AST here.
    args: tuple[ast.expr, ...] | None
    kwargs: immutabledict[str, ast.expr] | None


@attrs.frozen
class FunctionDef(Statement):
    name: str
    params: tuple[Parameter, ...]
    return_annotation: Expression | None
    decorators: tuple[Decorator, ...]
    docstring: str | None
    body: tuple[Statement, ...]

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_function_def(self)


@attrs.frozen
class ClassDef(Statement):
    name: str
    bases: tuple[Expression, ...]
    decorators: tuple[Decorator, ...]
    docstring: str | None
    body: tuple[Statement, ...]
    kwargs: immutabledict[str, ast.expr]

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_class_def(self)


@attrs.frozen
class ExpressionStatement(Statement):
    expr: Expression

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_expression_statement(self)


ConstantValue: typing.TypeAlias = (
    None | str | bytes | bool | int | float | complex | types.EllipsisType
)


@attrs.frozen
class Constant(Expression):
    value: ConstantValue

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_constant(self)


@attrs.frozen
class Module:
    name: str
    path: Path
    docstring: str | None
    future_flags: tuple[str, ...]
    body: tuple[Statement, ...]
