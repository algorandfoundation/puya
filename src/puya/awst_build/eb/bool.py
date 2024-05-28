from __future__ import annotations

import typing

import mypy.nodes

from puya import log
from puya.awst.nodes import (
    BoolConstant,
    Expression,
    Literal,
    Not,
    NumericComparison,
    NumericComparisonExpression,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    NodeBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.utils import bool_eval, convert_literal_to_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class BoolClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.BoolType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> NodeBuilder:
        match args:
            case []:
                false = BoolConstant(value=False, source_location=location)
                return BoolExpressionBuilder(false)
            case [arg]:
                return bool_eval(arg, location)
            case _:
                raise CodeError("Too many arguments", location=location)


class BoolExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.BoolType, expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> NodeBuilder:
        if not negate:
            return self
        return BoolExpressionBuilder(Not(location, self.expr))

    def compare(
        self, other: NodeBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> NodeBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        if other.pytype == self.pytype:
            pass
        else:
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=NumericComparison(op.value),
            rhs=other.rvalue(),
        )
        return BoolExpressionBuilder(cmp_expr)
