from __future__ import annotations

import abc
import enum
import typing

from puya.awst.nodes import (
    AppStorageKind,
    BytesConstant,
    ContractReference,
    Expression,
    FieldExpression,
    IndexExpression,
    Literal,
    Lvalue,
    Range,
    ReinterpretCast,
    Statement,
    TupleExpression,
    TupleItemExpression,
)
from puya.awst_build.contract_data import AppStorageDeclaration, AppStorageDeclType
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
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
    "StateProxyDefinitionBuilder",
    "StateProxyMemberBuilder",
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
    def value_type(self) -> wtypes.WType | None:
        return None

    @property
    def _type_description(self) -> str:
        if self.value_type is None:
            return type(self).__name__
        return self.value_type.stub_name

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


class IntermediateExpressionBuilder(ExpressionBuilder):
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


class StateProxyMemberBuilder(IntermediateExpressionBuilder):
    state_decl: AppStorageDeclaration


class StateProxyDefinitionBuilder(ExpressionBuilder, abc.ABC):
    kind: AppStorageKind
    python_name: str
    decl_type: typing.Literal[AppStorageDeclType.global_proxy, AppStorageDeclType.local_proxy]

    def __init__(
        self,
        location: SourceLocation,
        storage: wtypes.WType,
        key_override: BytesConstant | None,
        description: str | None,
        initial_value: Expression | None = None,
    ):
        super().__init__(location)
        self.storage = storage
        self.key_override = key_override
        self.description = description
        self.initial_value = initial_value

    def build_definition(
        self, member_name: str, defined_in: ContractReference, location: SourceLocation
    ) -> AppStorageDeclaration:
        return AppStorageDeclaration(
            description=self.description,
            member_name=member_name,
            key_override=self.key_override,
            source_location=location,
            storage_wtype=self.storage,
            key_wtype=None,
            kind=self.kind,
            defined_in=defined_in,
            decl_type=self.decl_type,
        )

    def rvalue(self) -> Expression:
        return self._assign_first(self.source_location)

    def lvalue(self) -> Lvalue:
        raise CodeError(
            f"{self.python_name} is not valid as an assignment target", self.source_location
        )

    def delete(self, location: SourceLocation) -> Statement:
        raise self._assign_first(location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return self._assign_first(location)

    def unary_plus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._assign_first(location)

    def unary_minus(self, location: SourceLocation) -> ExpressionBuilder:
        return self._assign_first(location)

    def bitwise_invert(self, location: SourceLocation) -> ExpressionBuilder:
        return self._assign_first(location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self._assign_first(location)

    def _assign_first(self, location: SourceLocation) -> typing.Never:
        raise CodeError(
            f"{self.python_name} should be assigned to an instance variable before being used",
            location,
        )


class TypeClassExpressionBuilder(IntermediateExpressionBuilder, abc.ABC):
    # TODO: better error messages for rvalue/lvalue/delete

    @abc.abstractmethod
    def produces(self) -> wtypes.WType: ...


class GenericClassExpressionBuilder(IntermediateExpressionBuilder, abc.ABC):
    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        return self.index_multiple([index], location)

    @abc.abstractmethod
    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder: ...

    @abc.abstractmethod
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder: ...

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
    ) -> ExpressionBuilder:
        raise CodeError(f"{self.wtype} does not support calling", location)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        raise CodeError(f"Unrecognised member of {self.wtype}: {name}", location)

    def iterate(self) -> Iteration:
        """Produce target of ForInLoop"""
        raise CodeError(f"{self.wtype} does not support iteration", self.source_location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        # TODO: this should be abstract, we always want to consider this for types
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
    if isinstance(resolved, TupleItemExpression):
        raise CodeError("Tuple items cannot be reassigned", resolved.source_location)
    if not isinstance(resolved, Lvalue):  # type: ignore[arg-type,misc]
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
    if isinstance(resolved, ReinterpretCast):
        _validate_lvalue(resolved.expr)
    elif isinstance(resolved, TupleExpression):
        for item in resolved.items:
            _validate_lvalue(item)
    return typing.cast(Lvalue, resolved)
