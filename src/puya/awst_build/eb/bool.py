import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya import log
from puya.awst.nodes import (
    BoolConstant,
    Expression,
    Not,
    NumericComparison,
    NumericComparisonExpression,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class BoolTypeBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.BoolType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case bool(literal_value):
                expr = BoolConstant(value=literal_value, source_location=location)
                return BoolExpressionBuilder(expr)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        match arg:
            case None:
                false = BoolConstant(value=False, source_location=location)
                return BoolExpressionBuilder(false)
            case InstanceBuilder(pytype=pytypes.BoolType):
                return arg
            case _:
                return arg.bool_eval(location)


class BoolExpressionBuilder(NotIterableInstanceExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.BoolType, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return intrinsic_factory.itob(self.resolve(), location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        if not negate:
            return self
        return BoolExpressionBuilder(Not(location, self.resolve()))

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        if other.pytype == self.pytype:
            pass
        else:
            return NotImplemented
        cmp_expr = NumericComparisonExpression(
            source_location=location,
            lhs=self.resolve(),
            operator=NumericComparison(op.value),
            rhs=other.resolve(),
        )
        return BoolExpressionBuilder(cmp_expr)
