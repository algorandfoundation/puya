from __future__ import annotations

import abc
import enum
import typing

import typing_extensions

from puya.awst import wtypes
from puya.awst.nodes import (
    ContractReference,
    Expression,
    FieldExpression,
    IndexExpression,
    Literal,
    Lvalue,
    Range,
    Statement,
    TupleExpression,
    TupleItemExpression,
)
from puya.awst_build import pytypes
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes
    import mypy.types

    from puya.awst_build.contract_data import AppStorageDeclaration
    from puya.parse import SourceLocation

__all__ = [
    "Iteration",
    "BuilderComparisonOp",
    "BuilderBinaryOp",
    "ExpressionBuilder",
    "StorageProxyConstructorResult",
    "FunctionBuilder",
    "IntermediateExpressionBuilder",
    "TypeClassExpressionBuilder",
    "GenericClassExpressionBuilder",
    "ValueExpressionBuilder",
]

Iteration: typing.TypeAlias = Expression | Range


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
    pow = "**"
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
    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder: ...

    @abc.abstractmethod
    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder: ...

    @abc.abstractmethod
    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder: ...

    @abc.abstractmethod
    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder: ...

    @property
    @typing.final
    def value_type(self) -> wtypes.WType | None:
        if self.pytype is None:
            return None
        return self.pytype.wtype

    @property
    @abc.abstractmethod
    def pytype(self) -> pytypes.PyType | None: ...

    @property
    def _type_description(self) -> str:
        if self.pytype is None:
            return type(self).__name__
        return str(self.pytype)

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
        raise CodeError(
            f"{self._type_description} does not support augmented assignment", location
        )

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        """Handle self[index]"""
        raise CodeError(f"{self._type_description} does not support indexing", location)

    @typing.final
    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> ExpressionBuilder:
        """Handle self[index]"""
        raise CodeError(f"{self._type_description} does not support multiple indexing", location)

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        """Handle self[begin_index:end_index:stride]"""
        raise CodeError(f"{self._type_description} does not support slicing", location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        """Handle self(args...)"""
        raise CodeError(f"{self._type_description} does not support calling", location)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        """Handle self.name"""
        raise CodeError(
            f"{self._type_description} does not support member access {name}", location
        )

    def iterate(self) -> Iteration:
        """Produce target of ForInLoop"""
        raise CodeError(
            f"{self._type_description} does not support iteration", self.source_location
        )


class IntermediateExpressionBuilder(ExpressionBuilder, abc.ABC):
    """Never valid as an assignment source OR target"""

    def rvalue(self) -> Expression:
        raise CodeError(
            f"{self._type_description} is not valid as an rvalue", self.source_location
        )

    def lvalue(self) -> Lvalue:
        raise CodeError(
            f"{self._type_description} is not valid as an lvalue", self.source_location
        )

    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError(
            f"{self._type_description} is not valid as del target", self.source_location
        )

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

    def _not_a_value(self, location: SourceLocation) -> typing.Never:
        raise CodeError(f"{self._type_description} is not a value", location)


class FunctionBuilder(IntermediateExpressionBuilder):
    @property
    def pytype(self) -> None:  # TODO: give function type
        return None


class StorageProxyConstructorResult(abc.ABC):
    @property
    @abc.abstractmethod
    def initial_value(self) -> Expression | None: ...

    @abc.abstractmethod
    def build_definition(
        self,
        member_name: str,
        defined_in: ContractReference,
        typ: pytypes.PyType,
        location: SourceLocation,
    ) -> AppStorageDeclaration: ...


_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class TypeClassExpressionBuilder(
    IntermediateExpressionBuilder, typing.Generic[_TPyType_co], abc.ABC
):
    # TODO: better error messages for rvalue/lvalue/delete

    def __init__(self, pytype: _TPyType_co, location: SourceLocation):
        super().__init__(location)
        self._pytype = pytype

    @property
    def pytype(self) -> pytypes.TypeType:
        return pytypes.TypeType(self._pytype)

    @typing.final
    def produces2(self) -> _TPyType_co:
        return self._pytype

    @typing.final
    def produces(self) -> wtypes.WType:
        return self._pytype.wtype

    @typing.override
    @abc.abstractmethod
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder: ...


class GenericClassExpressionBuilder(IntermediateExpressionBuilder, abc.ABC):
    @typing.override
    @property
    def pytype(self) -> None:  # TODO: ??
        return None

    @typing.override
    @abc.abstractmethod
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder: ...

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        raise CodeError(
            f"Cannot access member {name} without specifying class type parameters first",
            location,
        )


class ValueExpressionBuilder(ExpressionBuilder, typing.Generic[_TPyType_co]):

    def __init__(self, pytype: _TPyType_co, expr: Expression):
        super().__init__(expr.source_location)
        self._pytype = pytype
        self.__expr = expr
        if expr.wtype != self.wtype:
            raise InternalError(
                f"Invalid WType of {str(self.pytype)!r} expression for: {expr.wtype}",
                expr.source_location,
            )

    @typing.override
    @typing.final
    @property
    def pytype(self) -> _TPyType_co:
        return self._pytype

    @typing.final
    @property
    def wtype(self) -> wtypes.WType:
        return self._pytype.wtype

    @property
    def expr(self) -> Expression:
        return self.__expr

    @typing.override
    def lvalue(self) -> Lvalue:
        resolved = self.rvalue()
        return _validate_lvalue(resolved)

    @typing.override
    def rvalue(self) -> Expression:
        return self.expr

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError(f"{self.pytype} is not valid as del target", location)

    @typing.override
    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        raise CodeError(f"{self.pytype} does not support indexing", location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        raise CodeError(f"{self.pytype} does not support calling", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        raise CodeError(f"Unrecognised member of {self.pytype}: {name}", location)

    @typing.override
    def iterate(self) -> Iteration:
        """Produce target of ForInLoop"""
        raise CodeError(f"{self.pytype} does not support iteration", self.source_location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        # TODO: this should be abstract, we always want to consider this for types
        raise CodeError(f"{self.pytype} does not support boolean evaluation", location)

    @typing.override
    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        raise CodeError(f"{self.pytype} does not support unary plus operator", location)

    @typing.override
    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        raise CodeError(f"{self.pytype} does not support unary minus operator", location)

    @typing.override
    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        raise CodeError(f"{self.pytype} does not support bitwise inversion", location)

    @typing.override
    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        raise CodeError(f"{self.pytype} does not support in/not in checks", location)


def _validate_lvalue(resolved: Expression) -> Lvalue:
    if isinstance(resolved, TupleItemExpression):
        raise CodeError("Tuple items cannot be reassigned", resolved.source_location)
    if not isinstance(resolved, Lvalue):  # type: ignore[arg-type,misc]
        raise CodeError("expression is not valid as assignment target", resolved.source_location)
    if isinstance(resolved, IndexExpression):
        if resolved.base.wtype.immutable:
            raise CodeError(
                "expression is not valid as assignment target - collection is immutable",
                resolved.source_location,
            )
    elif isinstance(resolved, FieldExpression):
        if resolved.base.wtype.immutable:
            raise CodeError(
                "expression is not valid as assignment target - object is immutable",
                resolved.source_location,
            )
    elif isinstance(resolved, TupleExpression):
        for item in resolved.items:
            _validate_lvalue(item)
    return typing.cast(Lvalue, resolved)
