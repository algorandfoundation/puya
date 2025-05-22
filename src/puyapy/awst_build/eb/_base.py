# from __future__ import annotations

import abc
import typing

import typing_extensions

from puya import log
from puya.awst.nodes import (
    BinaryBooleanOperator,
    CompileTimeConstantExpression,
    Expression,
    Lvalue,
    SingleEvaluation,
    Statement,
    TupleExpression,
    VarExpression,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb._utils import constant_bool_and_error, dummy_statement, dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    CallableBuilder,
    InstanceBuilder,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)

__all__ = [
    "FunctionBuilder",
    "TypeBuilder",
    "GenericTypeBuilder",
    "InstanceExpressionBuilder",
    "NotIterableInstanceExpressionBuilder",
    "LiteralConvertingTypeBuilder",
]

_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)
_TExpression_co = typing_extensions.TypeVar(
    "_TExpression_co", bound=Expression, default=Expression, covariant=True
)

logger = log.get_logger(__name__)


class FunctionBuilder(CallableBuilder, abc.ABC):
    @typing.final
    @property
    def pytype(self) -> None:  # TODO: give function type
        return None

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)

    @typing.override
    @typing.final
    def member_access(self, name: str, location: SourceLocation) -> typing.Never:
        raise CodeError("function attribute access is not supported", location)


class TypeBuilder(CallableBuilder, typing.Generic[_TPyType_co], abc.ABC):
    def __init__(self, pytype: _TPyType_co, location: SourceLocation):
        super().__init__(location)
        self._pytype = pytype

    @typing.override
    @typing.final
    @property
    def pytype(self) -> pytypes.TypeType:
        return pytypes.TypeType(self._pytype)

    @typing.final
    def produces(self) -> _TPyType_co:
        return self._pytype

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        raise CodeError(f"unrecognised member {name!r} of type '{self._pytype}'", location)


class LiteralConvertingTypeBuilder(LiteralConverter, abc.ABC):
    @abc.abstractmethod
    def produces(self) -> pytypes.PyType: ...

    @typing.override
    @typing.final
    def convert_literal(self, literal: LiteralBuilder) -> InstanceBuilder:
        result = self.try_convert_literal(literal)
        if result is not None:
            return result
        logger.error(
            f"can't covert literal to {self.produces()}", location=literal.source_location
        )
        source_location = getattr(self, "source_location", literal.source_location)
        return dummy_value(self.produces(), source_location)


class GenericTypeBuilder(CallableBuilder, abc.ABC):
    @typing.override
    @property
    def pytype(self) -> None:  # TODO, take this as an init argument
        return None

    @typing.override
    @typing.final
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        raise CodeError("generic type requires parameters", location)

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


class InstanceExpressionBuilder(
    InstanceBuilder[_TPyType_co], typing.Generic[_TPyType_co, _TExpression_co], abc.ABC
):
    def __init__(self, pytype: _TPyType_co, expr: _TExpression_co):
        super().__init__(expr.source_location)
        if expr.wtype != pytype.wtype:
            raise InternalError(
                f"invalid expression wtype {str(expr.wtype)!r} for Python type {str(pytype)!r}",
                expr.source_location,
            )
        self._pytype = pytype
        self.__expr = expr

    @typing.override
    @typing.final
    @property
    def pytype(self) -> _TPyType_co:
        return self._pytype

    @typing.override
    def resolve_literal(self, converter: LiteralConverter) -> InstanceBuilder:
        return self

    @typing.override
    def try_resolve_literal(self, converter: LiteralConverter) -> InstanceBuilder:
        return self

    @typing.override
    @typing.final
    def resolve_lvalue(self) -> Lvalue:
        resolved = self.resolve()
        return _validate_lvalue(self._pytype, resolved)

    @typing.override
    def resolve(self) -> _TExpression_co:
        return self.__expr

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        logger.error(f"{self.pytype} is not valid as del target", location=location)
        return dummy_statement(location)

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
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        return super().bool_binary_op(other, op, location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        logger.error(f"{self.pytype} does not support augmented assignment", location=location)
        return dummy_statement(location)

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        if not isinstance(
            self.__expr, VarExpression | CompileTimeConstantExpression | SingleEvaluation
        ):
            return builder_for_instance(self.pytype, SingleEvaluation(self.__expr))
        return self


class NotIterableInstanceExpressionBuilder(InstanceExpressionBuilder[_TPyType_co], abc.ABC):
    @typing.final
    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return super().contains(item, location)

    @typing.final
    @typing.override
    def iterate(self) -> Expression:
        return super().iterate()

    @typing.final
    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return super().iterable_item_type()

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
    if not isinstance(resolved, Lvalue):
        raise CodeError(
            "expression is not valid as an assignment target", resolved.source_location
        )
    if isinstance(resolved, TupleExpression):
        assert isinstance(typ, pytypes.TupleLikeType)
        for item_typ, item in zip(typ.items, resolved.items, strict=True):
            _validate_lvalue(item_typ, item)
    return resolved
