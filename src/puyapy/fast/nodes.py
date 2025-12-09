import abc
import ast
import enum
import types
import typing
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya.parse import SourceLocation
from puyapy.fast.visitors import ExpressionVisitor, MatchPatternVisitor, StatementVisitor


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
    args: tuple[Expression, ...] | None
    kwargs: immutabledict[str, Expression] | None


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
    kwargs: immutabledict[str, Expression]

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
    indexes: tuple[Expression | Slice, ...] = attrs.field(validator=attrs.validators.min_len(1))
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
    targets: tuple[Expression, ...] = attrs.field(validator=attrs.validators.min_len(1))

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

    targets: tuple[Expression, ...] = attrs.field(validator=attrs.validators.min_len(2))
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
    else_body: tuple[Statement, ...] | None

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_for(self)


@attrs.frozen
class While(Statement):
    test: Expression
    body: tuple[Statement, ...]
    else_body: tuple[Statement, ...] | None

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_while(self)


@attrs.frozen
class If(Statement):
    test: Expression
    body: tuple[Statement, ...]
    else_body: tuple[Statement, ...] | None  # if there are elifs, they are nested in here as Ifs

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
class MatchPattern(Node, abc.ABC):
    @abc.abstractmethod
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T: ...


@attrs.frozen
class MatchValue(MatchPattern):
    value: Expression

    @typing.override
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T:
        return visitor.visit_match_value(self)


@attrs.frozen
class MatchSequence(MatchPattern):
    patterns: tuple[MatchPattern, ...] = attrs.field(validator=attrs.validators.min_len(1))

    @typing.override
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T:
        return visitor.visit_match_sequence(self)


@attrs.frozen
class MatchSingleton(MatchPattern):
    value: typing.Literal[True, False] | None

    @typing.override
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T:
        return visitor.visit_match_singleton(self)


@attrs.frozen
class MatchStar(MatchPattern):
    name: str | None

    @typing.override
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T:
        return visitor.visit_match_star(self)


@attrs.frozen
class MatchMapping(MatchPattern):
    kwd_patterns: immutabledict[Expression, MatchPattern]
    rest: str | None

    @typing.override
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T:
        return visitor.visit_match_mapping(self)


@attrs.frozen
class MatchClass(MatchPattern):
    cls: Expression
    patterns: tuple[MatchPattern, ...]
    kwd_patterns: immutabledict[str, MatchPattern]

    @typing.override
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T:
        return visitor.visit_match_class(self)


@attrs.frozen
class MatchAs(MatchPattern):
    pattern: MatchPattern | None
    name: str | None

    @typing.override
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T:
        return visitor.visit_match_as(self)


@attrs.frozen
class MatchOr(MatchPattern):
    patterns: tuple[MatchPattern, ...] = attrs.field(validator=attrs.validators.min_len(1))

    @typing.override
    def accept[T](self, visitor: MatchPatternVisitor[T]) -> T:
        return visitor.visit_match_or(self)


@attrs.frozen
class MatchCase:
    pattern: MatchPattern
    guard: Expression | None
    body: tuple[Statement, ...]


@attrs.frozen
class Match(Statement):
    subject: Expression
    cases: tuple[MatchCase, ...]

    @typing.override
    def accept[T](self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_match(self)


@attrs.frozen
class BoolOp(Expression):
    op: ast.boolop
    values: tuple[Expression, ...] = attrs.field(validator=attrs.validators.min_len(2))

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bool_op(self)


@attrs.frozen
class NamedExpr(Expression):
    target: Name
    value: Expression

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_named_expr(self)


@attrs.frozen
class BinOp(Expression):
    left: Expression
    op: ast.operator
    right: Expression

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bin_op(self)


@attrs.frozen
class UnaryOp(Expression):
    op: ast.unaryop  # TODO: type union here and elsewhere for similar types in this file?
    operand: Expression

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_unary_op(self)


@attrs.frozen
class IfExp(Expression):
    test: Expression
    true: Expression
    false: Expression

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_if_exp(self)


@attrs.frozen
class Compare(Expression):
    left: Expression
    ops: tuple[ast.cmpop, ...] = attrs.field(validator=attrs.validators.min_len(1))
    comparators: tuple[Expression, ...] = attrs.field(validator=attrs.validators.min_len(1))

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_compare(self)


@attrs.frozen
class Call(Expression):
    func: Expression
    args: tuple[Expression, ...]
    kwargs: immutabledict[str, Expression]

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_call(self)


@attrs.frozen
class FormattedValue(Expression):
    value: Expression
    conversion: typing.Literal["s", "r", "a"] | None
    format_spec: "JoinedStr | None"  # ???

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_formatted_value(self)


@attrs.frozen
class JoinedStr(Expression):
    values: tuple[FormattedValue | Constant, ...]  # ???

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_joined_str(self)


@attrs.frozen
class TupleExpr(Expression):
    elements: tuple[Expression, ...]
    ctx: ast.expr_context

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_tuple_expr(self)


@attrs.frozen
class ListExpr(Expression):
    elements: tuple[Expression, ...]
    ctx: ast.expr_context

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_list_expr(self)


@attrs.frozen
class DictExpr(Expression):
    pairs: tuple[tuple[Expression | None, Expression], ...]

    @typing.override
    def accept[T](self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_dict_expr(self)


@attrs.frozen
class Module:
    name: str
    path: Path
    docstring: str | None
    body: tuple[Statement, ...]
