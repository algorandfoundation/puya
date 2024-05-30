from __future__ import annotations

import abc
import enum
import typing

import typing_extensions

from puya.awst.nodes import (
    ContractReference,
    Expression,
    FieldExpression,
    Literal,
    Lvalue,
    Range,
    Statement,
    TupleExpression,
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
    "BuilderUnaryOp",
    "BuilderBinaryOp",
    "NodeBuilder",
    "CallableBuilder",
    "InstanceBuilder",
    "StorageProxyConstructorResult",
    "FunctionBuilder",
    "TypeBuilder",
    "GenericTypeBuilder",
    "InstanceExpressionBuilder",
    "NotIterableInstanceExpressionBuilder",
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
class BuilderUnaryOp(enum.StrEnum):
    positive = "+"
    negative = "-"
    bit_invert = "~"


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


class NodeBuilder(abc.ABC):
    def __init__(self, location: SourceLocation):
        self.source_location = location

    @property
    @abc.abstractmethod
    def pytype(self) -> pytypes.PyType | None: ...

    @abc.abstractmethod
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        """Handle self.name"""

    @abc.abstractmethod
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        """Handle boolean-ness evaluation, possibly inverted (ie "not" unary operator)"""


class CallableBuilder(NodeBuilder, abc.ABC):
    @abc.abstractmethod
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        """Handle self(args...)"""


class FunctionBuilder(CallableBuilder, abc.ABC):
    @property
    @typing.final
    def pytype(self) -> None:  # TODO: give function type
        return None

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        from puya.awst_build.eb._utils import bool_eval_to_constant

        return bool_eval_to_constant(value=True, location=location, negate=negate)

    @typing.override
    @typing.final
    def member_access(self, name: str, location: SourceLocation) -> typing.Never:
        raise CodeError("function attribute access is not supported", location)


_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class TypeBuilder(CallableBuilder, typing.Generic[_TPyType_co], abc.ABC):
    # TODO: better error messages for rvalue/lvalue/delete

    def __init__(self, pytype: _TPyType_co, location: SourceLocation):
        super().__init__(location)
        self._pytype = pytype

    @typing.final
    @typing.override
    @property
    def pytype(self) -> pytypes.TypeType:
        return pytypes.TypeType(self._pytype)

    @typing.final
    def produces(self) -> _TPyType_co:
        return self._pytype

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        from puya.awst_build.eb._utils import bool_eval_to_constant

        return bool_eval_to_constant(value=True, location=location, negate=negate)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        raise CodeError(f"unrecognised member {name!r} of type '{self._pytype}'", location)


class GenericTypeBuilder(CallableBuilder, abc.ABC):
    @typing.override
    @property
    def pytype(self) -> None:  # TODO: ??
        return None

    @typing.override
    @typing.final
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        raise CodeError("generic type requires parameters", location)

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        from puya.awst_build.eb._utils import bool_eval_to_constant

        return bool_eval_to_constant(value=True, location=location, negate=negate)


class InstanceBuilder(NodeBuilder, typing.Generic[_TPyType_co], abc.ABC):
    @typing.override
    @property
    @abc.abstractmethod
    def pytype(self) -> _TPyType_co: ...

    @abc.abstractmethod
    def rvalue(self) -> Expression:
        """Produce an expression for use as an intermediary"""

    @abc.abstractmethod
    def lvalue(self) -> Lvalue:
        """Produce an expression for the target of an assignment"""

    @abc.abstractmethod
    def delete(self, location: SourceLocation) -> Statement:
        """Handle del self"""

    @abc.abstractmethod
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        """Handle {op} self"""

    @abc.abstractmethod
    def compare(
        self, other: InstanceBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        """Handle self {op} other"""

    @abc.abstractmethod
    def binary_op(
        self,
        other: InstanceBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        """Handle self {op} other"""

    @abc.abstractmethod
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder | Literal, location: SourceLocation
    ) -> Statement:
        """Handle self {op}= rhs"""

    @abc.abstractmethod
    def contains(self, item: NodeBuilder | Literal, location: SourceLocation) -> InstanceBuilder:
        """Handle item in self"""
        raise CodeError("expression is not iterable", self.source_location)

    @abc.abstractmethod
    def iterate(self) -> Iteration:
        """Produce target of ForInLoop"""
        raise CodeError("expression is not iterable", self.source_location)

    @abc.abstractmethod
    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        """Handle self[index]"""
        raise CodeError("expression is not a collection", self.source_location)

    @abc.abstractmethod
    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        """Handle self[begin_index:end_index:stride]"""
        raise CodeError("expression is not a collection", self.source_location)


class StorageProxyConstructorResult(
    InstanceBuilder[pytypes.StorageProxyType | pytypes.StorageMapProxyType], abc.ABC
):
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


class InstanceExpressionBuilder(InstanceBuilder[_TPyType_co], abc.ABC):

    def __init__(self, pytype: _TPyType_co, expr: Expression):
        super().__init__(expr.source_location)
        if expr.wtype != pytype.wtype:
            raise InternalError(
                f"invalid WType of {str(self.pytype)!r} expression for: {expr.wtype}",
                expr.source_location,
            )
        self._pytype = pytype
        self.__expr = expr

    @typing.override
    @typing.final
    @property
    def pytype(self) -> _TPyType_co:
        return self._pytype

    @property
    def expr(self) -> Expression:
        return self.__expr

    @typing.override
    @typing.final
    def lvalue(self) -> Lvalue:
        resolved = self.rvalue()
        return _validate_lvalue(self._pytype, resolved)

    @typing.override
    def rvalue(self) -> Expression:
        return self.expr

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError(f"{self.pytype} is not valid as del target", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        raise CodeError(f"unrecognised member of {self.pytype}: {name}", location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        raise CodeError(f"{self.pytype} does not support unary {op.value!r} operator", location)

    @typing.override
    def compare(
        self, other: InstanceBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return NotImplemented

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        return NotImplemented

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder | Literal, location: SourceLocation
    ) -> Statement:
        raise CodeError(f"{self.pytype} does not support augmented assignment", location)


class NotIterableInstanceExpressionBuilder(InstanceExpressionBuilder[_TPyType_co], abc.ABC):
    @typing.final
    @typing.override
    def contains(self, item: NodeBuilder | Literal, location: SourceLocation) -> InstanceBuilder:
        return super().contains(item, location)

    @typing.final
    @typing.override
    def iterate(self) -> Iteration:
        return super().iterate()

    @typing.final
    @typing.override
    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        return super().index(index, location)

    @typing.final
    @typing.override
    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        return super().slice_index(begin_index, end_index, stride, location)


def _validate_lvalue(typ: pytypes.PyType, resolved: Expression) -> Lvalue:
    if typ == pytypes.NoneType:
        raise CodeError(
            "None indicates an empty return and cannot be assigned",
            resolved.source_location,
        )
    if not isinstance(resolved, Lvalue):  # type: ignore[arg-type,misc]
        raise CodeError(
            "expression is not valid as an assignment target", resolved.source_location
        )
    if isinstance(resolved, FieldExpression):
        if resolved.base.wtype.immutable:
            raise CodeError(
                "expression is not valid as an assignment target - object is immutable",
                resolved.source_location,
            )
    elif isinstance(resolved, TupleExpression):
        assert isinstance(typ, pytypes.TupleType)
        for item_typ, item in zip(typ.items, resolved.items, strict=True):
            _validate_lvalue(item_typ, item)
    return typing.cast(Lvalue, resolved)
