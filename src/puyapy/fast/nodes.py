import abc
import ast
import enum
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


class PassBy(enum.Flag):
    POSITION = enum.auto()
    NAME = enum.auto()


@attrs.frozen
class Parameter(Node):
    name: str
    annotation: Expression | None
    default: Expression | None
    pass_by: PassBy


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
class Name(Expression):
    id: str
    ctx: ast.expr_context

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_name(self)


@attrs.frozen
class Attribute(Expression):
    base: Expression
    attr: str
    ctx: ast.expr_context

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_attribute(self)


@attrs.frozen
class Slice(Node):
    lower: Expression | None
    upper: Expression | None
    step: Expression | None


@attrs.frozen
class Subscript(Expression):
    base: Expression
    indexes: tuple[Expression | Slice, ...]
    ctx: ast.expr_context

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_subscript(self)


@attrs.frozen
class Return(Statement):
    value: Expression | None

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_return(self)


@attrs.frozen
class Delete(Statement):
    targets: tuple[Expression, ...]

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_delete(self)


@attrs.frozen
class Assign(Statement):
    """
    Single assignment, with an optional annotation, e.g. `x: int = 1`
    """

    target: Expression
    value: Expression
    annotation: Expression | None

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_assign(self)


@attrs.frozen
class MultiAssign(Statement):
    """
    Chained assignment, e.g. `a = b = ...`
    Syntactically, cannot have an annotation.
    """

    targets: tuple[Expression, ...]
    value: Expression

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_multi_assign(self)


@attrs.frozen
class AugAssign(Statement):
    """
    Augmented assignment, e.g. `x += 1`
    """

    target: Name | Attribute | Subscript
    op: ast.operator
    value: Expression

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_aug_assign(self)


@attrs.frozen
class AnnotationStatement(Statement):
    """
    An annotation without assignment, e.g. `x: int` or `self.foo: int`.
    This is effectively a no-op, provided the Name(s) involved exist.
    """

    target: Name | Attribute | Subscript
    annotation: Expression

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_annotation(self)


@attrs.frozen
class For(Statement):
    target: Expression
    iterable: Expression
    body: tuple[Statement, ...]
    else_body: tuple[Statement, ...]

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_for(self)


@attrs.frozen
class While(Statement):
    test: Expression
    body: tuple[Statement, ...]
    else_body: tuple[Statement, ...]

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_while(self)


@attrs.frozen
class If(Statement):
    test: Expression
    body: tuple[Statement, ...]
    else_body: tuple[Statement, ...]  # can be another If in here for elif chains

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_if(self)


@attrs.frozen
class Assert(Statement):
    test: Expression
    msg: Expression | None

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_assert(self)


@attrs.frozen
class Pass(Statement):
    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_pass(self)


@attrs.frozen
class Break(Statement):
    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_break(self)


@attrs.frozen
class Continue(Statement):
    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_continue(self)


@attrs.frozen
class Module:
    name: str
    path: Path
    docstring: str | None
    future_flags: tuple[str, ...]
    body: tuple[Statement, ...]
