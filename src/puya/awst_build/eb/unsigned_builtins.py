from __future__ import annotations

import typing

import mypy.nodes

from puya import log
from puya.awst.nodes import (
    Enumeration,
    Expression,
    IntegerConstant,
    Literal,
    Lvalue,
    Range,
    Reversed,
    Statement,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    Iteration,
    NodeBuilder,
    TypeBuilder,
)
from puya.awst_build.utils import expect_operand_type, require_expression_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class UnsignedRangeBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.urangeType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        uint64_args = [expect_operand_type(in_arg, pytypes.UInt64Type).rvalue() for in_arg in args]
        match uint64_args:
            case [range_start, range_stop, range_step]:
                if isinstance(range_step, IntegerConstant) and range_step.value == 0:
                    raise CodeError("urange step size cannot be zero", range_step.source_location)
            case [range_start, range_stop]:
                range_step = UInt64Constant(value=1, source_location=location)
            case [range_stop]:
                range_start = UInt64Constant(value=0, source_location=location)
                range_step = UInt64Constant(value=1, source_location=location)
            case []:
                raise CodeError("urange function takes at least one argument", location=location)
            case _:
                raise CodeError(
                    "too many arguments to urange function, takes at most three arguments",
                    location=location,
                )

        sequence = Range(
            source_location=location,
            start=range_start,
            stop=range_stop,
            step=range_step,
        )
        return _IterableOnlyBuilder(sequence)


class UnsignedEnumerateBuilder(TypeBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        if not args:
            raise CodeError("insufficient arguments", location)
        try:
            (arg,) = args
        except ValueError as ex:
            raise CodeError(
                "unlike enumerate(), uenumerate() does not support a start parameter "
                "(ie, start must always be zero)",
                location,
            ) from ex
        sequence = require_expression_builder(arg).iterate()
        enumeration = Enumeration(expr=sequence, source_location=location)
        return _IterableOnlyBuilder(enumeration)


class ReversedFunctionExpressionBuilder(TypeBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        if not args:
            raise CodeError("insufficient arguments", location)
        try:
            (arg,) = args
        except ValueError as ex:
            raise CodeError(
                "reversed expects a single argument",
                location,
            ) from ex
        sequence = require_expression_builder(arg).iterate()
        reversed_ = Reversed(expr=sequence, source_location=location)
        return _IterableOnlyBuilder(reversed_)


class _IterableOnlyBuilder(NodeBuilder):
    def __init__(self, expr: Iteration):
        super().__init__(expr.source_location)
        self._expr = expr

    @typing.override
    def iterate(self) -> Iteration:
        return self._expr

    @typing.override
    @property
    def pytype(self) -> None:
        return None

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> NodeBuilder:
        return self._iterable_only(location)

    @typing.override
    def rvalue(self) -> Expression:
        return self._iterable_only(self.source_location)

    @typing.override
    def lvalue(self) -> Lvalue:
        return self._iterable_only(self.source_location)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        return self._iterable_only(location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> NodeBuilder:
        return self._iterable_only(location)

    @typing.override
    def contains(self, item: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        return self._iterable_only(location)

    @typing.override
    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        return self._iterable_only(location)

    @typing.override
    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
        return self._iterable_only(location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        return self._iterable_only(location)

    @typing.override
    def compare(
        self, other: NodeBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> NodeBuilder:
        return self._iterable_only(location)

    @typing.override
    def binary_op(
        self,
        other: NodeBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> NodeBuilder:
        return self._iterable_only(location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: NodeBuilder | Literal, location: SourceLocation
    ) -> Statement:
        return self._iterable_only(location)

    def _iterable_only(self, location: SourceLocation) -> typing.Never:
        raise CodeError("expression is only usable as the source of a for-loop", location)
