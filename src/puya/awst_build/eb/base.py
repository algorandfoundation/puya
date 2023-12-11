from __future__ import annotations

import abc
import enum
from typing import TYPE_CHECKING, Never, TypeAlias, cast

from puya.awst.nodes import (
    Expression,
    FieldExpression,
    IndexExpression,
    Literal,
    Lvalue,
    Range,
    ReinterpretCast,
    Statement,
    TupleExpression,
)
from puya.errors import CodeError, InternalError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes
    import mypy.types

    from puya.awst import wtypes
    from puya.parse import SourceLocation

__all__ = [
    "Iteration",
    "BuilderComparisonOp",
    "BuilderBinaryOp",
    "ExpressionBuilder",
    "IntermediateExpressionBuilder",
    "TypeClassExpressionBuilder",
    "GenericClassExpressionBuilder",
    "ValueExpressionBuilder",
]

Iteration: TypeAlias = Expression | Range


@enum.unique
class BuilderComparisonOp(enum.StrEnum):
    eq = "=="
    ne = "!="
    lt = "<"
    lte = "<="
    gt = ">"
    gte = ">="


@enum.unique
class BuilderBinaryOp(enum.StrEnum):
    add = "+"
    sub = "-"
    mult = "*"
    div = "/"
    floor_div = "//"
    mod = "%"
    pow = "**"  # noqa: A003
    mat_mult = "@"
    lshift = "<<"
    rshift = ">>"
    bit_or = "|"
    bit_xor = "^"
    bit_and = "&"


class ExpressionBuilder(abc.ABC):
    def __init__(self, location: SourceLocation):
        self.source_location = location

    @abc.abstractmethod
    def rvalue(self) -> Expression:
        """Produce an expression for use as an intermediary"""

    def build_assignment_source(self) -> Expression:
        """Produce an expression for the source of an assignment"""
        return self.rvalue()

    @abc.abstractmethod
    def lvalue(self) -> Lvalue:
        """Produce an expression for the target of an assignment"""

    @abc.abstractmethod
    def delete(self, location: SourceLocation) -> Statement:
        """Handle del operator statement"""
        # TODO: consider making a DeleteStatement which e.g. handles AppAccountStateExpression

    @abc.abstractmethod
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        """Handle boolean-ness evaluation, possibly inverted (ie "not" unary operator)"""

    @abc.abstractmethod
    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        ...

    @abc.abstractmethod
    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        ...

    @abc.abstractmethod
    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        ...

    @abc.abstractmethod
    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        ...

    @property
    def value_type(self) -> wtypes.WType | None:
        return None

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        """handle self {op} other"""
        if self.value_type is None:
            raise CodeError(
                f"expression is not a value type, so comparison with {op.value} is not supported",
                location,
            )
        return NotImplemented

    def binary_op(
        self,
        other: ExpressionBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> ExpressionBuilder:
        """handle self {op} other"""
        if self.value_type is None:
            raise CodeError(
                f"expression is not a value type,"
                f" so operations such as {op.value} are not supported",
                location,
            )
        return NotImplemented

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        if self.value_type is None:
            raise CodeError(
                f"expression is not a value type,"
                f" so operations such as {op.value}= are not supported",
                location,
            )
        raise CodeError(f"{self.value_type} does not support augmented assignment", location)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        """Handle self[index]"""
        raise CodeError(f"{type(self).__name__} does not support indexing", location)

    def index_multiple(
        self, index: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> ExpressionBuilder:
        """Handle self[index]"""
        raise CodeError(f"{type(self).__name__} does not support multiple indexing", location)

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        """Handle self[begin_index:end_index:stride]"""
        raise CodeError(f"{type(self).__name__} does not support slicing", location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        """Handle self(args...)"""
        raise CodeError(f"{type(self).__name__} does not support calling", location)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        """Handle self.name"""
        raise CodeError(f"{type(self).__name__} does not support member access {name}", location)

    def iterate(self) -> Iteration:
        """Produce target of ForInLoop"""
        raise CodeError(f"{type(self).__name__} does not support iteration", self.source_location)


class IntermediateExpressionBuilder(ExpressionBuilder):
    """Never valid as an assignment source OR target"""

    def rvalue(self) -> Expression:
        raise CodeError(f"{type(self).__name__} is not valid as an rvalue", self.source_location)

    def lvalue(self) -> Lvalue:
        raise CodeError(f"{type(self).__name__} is not valid as an lvalue", self.source_location)

    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError(f"{type(self).__name__} is not valid as del target", self.source_location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return self._not_a_value(location)

    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._not_a_value(location)

    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._not_a_value(location)

    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        return self._not_a_value(location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._not_a_value(location)

    def _not_a_value(self, location: SourceLocation) -> Never:
        raise CodeError(f"{type(self).__name__} is not a value", location)


class TypeClassExpressionBuilder(IntermediateExpressionBuilder, abc.ABC):
    # TODO: better error messages for rvalue/lvalue/delete

    @abc.abstractmethod
    def produces(self) -> wtypes.WType:
        ...


class GenericClassExpressionBuilder(IntermediateExpressionBuilder, abc.ABC):
    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        return self.index_multiple([index], location)

    @abc.abstractmethod
    def index_multiple(
        self, index: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        ...

    @abc.abstractmethod
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        ...

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        raise CodeError(
            f"Cannot access member {name} without specifying class type parameters first",
            location,
        )


class ValueExpressionBuilder(ExpressionBuilder):
    wtype: wtypes.WType

    def __init__(self, expr: Expression):
        super().__init__(expr.source_location)
        self.__expr = expr
        if expr.wtype != self.wtype:
            raise InternalError(
                f"Invalid type of expression for {self.wtype}: {expr.wtype}",
                expr.source_location,
            )

    @property
    def expr(self) -> Expression:
        return self.__expr

    def lvalue(self) -> Lvalue:
        resolved = self.rvalue()
        return _validate_lvalue(resolved)

    def rvalue(self) -> Expression:
        return self.expr

    @property
    def value_type(self) -> wtypes.WType:
        return self.wtype

    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError(f"{self.wtype} is not valid as del target", location)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        raise CodeError(f"{self.wtype} does not support indexing", location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        raise CodeError(f"{self.wtype} does not support calling", location)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        raise CodeError(f"Unrecognised member of {self.wtype}: {name}", location)

    def iterate(self) -> Iteration:
        """Produce target of ForInLoop"""
        raise CodeError(f"{type(self).__name__} does not support iteration", self.source_location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        raise CodeError(f"{self.wtype} does not support boolean evaluation", location)

    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        raise CodeError(f"{self.wtype} does not support unary plus operator", location)

    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        raise CodeError(f"{self.wtype} does not support unary minus operator", location)

    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        raise CodeError(f"{self.wtype} does not support bitwise inversion", location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        raise CodeError(f"{self.wtype} does not support in/not in checks", location)


def _validate_lvalue(resolved: Expression) -> Lvalue:
    if not (isinstance(resolved, Lvalue) and resolved.wtype.lvalue):  # type: ignore[arg-type,misc]
        raise CodeError(
            f"{resolved.wtype.stub_name} expression is not valid as assignment target",
            resolved.source_location,
        )
    if isinstance(resolved, IndexExpression | FieldExpression) and resolved.base.wtype.immutable:
        raise CodeError(
            "expression is not valid as assignment target"
            f" ({resolved.base.wtype.stub_name} is immutable)",
            resolved.source_location,
        )
    elif isinstance(resolved, ReinterpretCast):
        _validate_lvalue(resolved.expr)
    elif isinstance(resolved, TupleExpression):
        for item in resolved.items:
            _validate_lvalue(item)
    return cast(Lvalue, resolved)
