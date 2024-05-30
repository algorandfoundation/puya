from __future__ import annotations

import abc
import typing

import typing_extensions

from puya.awst.nodes import (
    Expression,
    FieldExpression,
    Lvalue,
    Statement,
    TupleExpression,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    CallableBuilder,
    InstanceBuilder,
    Iteration,
    NodeBuilder,
)
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from puya.parse import SourceLocation

__all__ = [
    "FunctionBuilder",
    "TypeBuilder",
    "GenericTypeBuilder",
    "InstanceExpressionBuilder",
    "NotIterableInstanceExpressionBuilder",
]
_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


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
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        raise CodeError(f"unrecognised member {name!r} of type '{self._pytype}'", location)


class GenericTypeBuilder(CallableBuilder, abc.ABC):
    @typing.override
    @property
    def pytype(self) -> None:  # TODO: ??
        return None

    @typing.override
    @typing.final
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        raise CodeError("generic type requires parameters", location)

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        from puya.awst_build.eb._utils import bool_eval_to_constant

        return bool_eval_to_constant(value=True, location=location, negate=negate)


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
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        raise CodeError(f"unrecognised member of {self.pytype}: {name}", location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        raise CodeError(f"{self.pytype} does not support unary {op.value!r} operator", location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return NotImplemented

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        return NotImplemented

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        raise CodeError(f"{self.pytype} does not support augmented assignment", location)


class NotIterableInstanceExpressionBuilder(InstanceExpressionBuilder[_TPyType_co], abc.ABC):
    @typing.final
    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return super().contains(item, location)

    @typing.final
    @typing.override
    def iterate(self) -> Iteration:
        return super().iterate()

    @typing.final
    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return super().index(index, location)

    @typing.final
    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
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
