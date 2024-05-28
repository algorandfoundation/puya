from __future__ import annotations

import typing

import mypy.nodes

from puya import log
from puya.awst.nodes import (
    Enumeration,
    Expression,
    IntegerConstant,
    Literal,
    Range,
    Reversed,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    IntermediateExpressionBuilder,
    Iteration,
    NodeBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.utils import expect_operand_type, require_expression_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class UnsignedRangeBuilder(TypeClassExpressionBuilder):
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
        return UnsignedRange(sequence)


class UnsignedRange(IntermediateExpressionBuilder):
    def __init__(self, sequence: Range):
        super().__init__(location=sequence.source_location)
        self.sequence = sequence

    @typing.override
    @property
    def pytype(self) -> None:  # TODO: ??
        return None

    @typing.override
    def iterate(self) -> Iteration:
        return self.sequence


class UnsignedEnumerateBuilder(TypeClassExpressionBuilder):
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
        return UnsignedEnumerate(sequence, location)


class UnsignedEnumerate(IntermediateExpressionBuilder):
    def __init__(self, sequence: Expression | Range, location: SourceLocation):
        super().__init__(location)
        self._sequence = sequence

    @typing.override
    @property
    def pytype(self) -> None:  # TODO: ??
        return None

    @typing.override
    def iterate(self) -> Iteration:
        return Enumeration(
            expr=self._sequence,
            source_location=self.source_location,
        )


class ReversedFunctionExpressionBuilder(TypeClassExpressionBuilder):
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
        return ReversedExpressionBuilder(sequence, location)


class ReversedExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, sequence: Expression | Range, location: SourceLocation):
        super().__init__(location)
        self._sequence = sequence

    @typing.override
    @property
    def pytype(self) -> None:  # TODO: ??
        return None

    @typing.override
    def iterate(self) -> Iteration:
        return Reversed(
            expr=self._sequence,
            source_location=self.source_location,
        )
