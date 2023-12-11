from __future__ import annotations

from typing import TYPE_CHECKING

import mypy.nodes
import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    Enumeration,
    Expression,
    Literal,
    Range,
    UInt64Constant,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    Iteration,
)
from puya.awst_build.utils import (
    expect_operand_wtype,
    require_expression_builder,
)
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class UnsignedRangeBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        uint64_args = [expect_operand_wtype(in_arg, wtypes.uint64_wtype) for in_arg in args]
        match uint64_args:
            case [range_start, range_stop, range_step]:
                pass
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

    def iterate(self) -> Iteration:
        return self.sequence


class UnsignedEnumerateBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
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

    def iterate(self) -> Iteration:
        return Enumeration(
            expr=self._sequence,
            source_location=self.source_location,
        )
