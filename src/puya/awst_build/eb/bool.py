from __future__ import annotations

import typing

import mypy.nodes

from puya import log
from puya.awst.nodes import (
    BoolConstant,
    Expression,
    Not,
    NumericComparison,
    NumericComparisonExpression,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import (
    NotIterableInstanceExpressionBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.awst_build.utils import convert_literal_to_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    import mypy.types

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class BoolTypeBuilder(TypeBuilder, LiteralConverter):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.BoolType, location)

    @typing.override
    @property
    def handled_types(self) -> Collection[pytypes.PyType]:
        return (pytypes.BoolType,)

    @typing.override
    def convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder:
        match literal.value:
            case bool(literal_value):
                expr = BoolConstant(value=literal_value, source_location=location)
                return BoolExpressionBuilder(expr)
        raise CodeError(f"can't covert literal {literal.value!r} to {self.produces()}", location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case []:
                false = BoolConstant(value=False, source_location=location)
                return BoolExpressionBuilder(false)
            case [InstanceBuilder(pytype=pytypes.BoolType) as already_bool]:
                return already_bool
            case [NodeBuilder() as nb]:
                return nb.bool_eval(location)
            case _:
                raise CodeError("Too many arguments", location=location)


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
        other = convert_literal_to_builder(other, self.pytype)
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
