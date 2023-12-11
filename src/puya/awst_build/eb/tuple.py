from collections.abc import Sequence

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    BoolConstant,
    Contains,
    Expression,
    IntegerConstant,
    Literal,
    SliceExpression,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError, TodoError
from puya.parse import SourceLocation
from puya.utils import clamp

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class TupleTypeExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        try:
            return self.wtype
        except AttributeError as ex:
            raise CodeError(
                "Unparameterized tuple class cannot be used as a type", self.source_location
            ) from ex

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        return self.index_multiple((index,), location)

    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        tuple_item_types = list[wtypes.WType]()
        for index in indexes:
            match index:
                case TypeClassExpressionBuilder() as type_class:
                    wtype = type_class.produces()
                    if wtype is wtypes.void_wtype:
                        raise CodeError("Tuples cannot contain None values", location)
                    tuple_item_types.append(wtype)
                case _:
                    raise CodeError("Expected a type", index.source_location)
        self.wtype = wtypes.WTuple.from_types(tuple_item_types)
        return self


class TupleExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.WTuple)
        self.wtype: wtypes.WTuple = expr.wtype
        super().__init__(expr)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        # special handling of tuples, they can be indexed by int literal only,
        # mostly because they can be non-homogenous so we need to be able to resolve the
        # result type, but also we can statically validate that value
        index_expr_or_literal = index
        match index_expr_or_literal:
            case Literal(value=int(index_value)) as index_literal:
                try:
                    self.wtype.types[index_value]
                except IndexError as ex:
                    raise CodeError(
                        "Tuple index out of bounds", index_literal.source_location
                    ) from ex
                item_expr = TupleItemExpression(
                    source_location=location,
                    base=self.expr,
                    index=index_value,
                )
                return var_expression(item_expr)
            case _:
                raise CodeError(
                    "tuples can only be indexed by literal ints",
                    index_expr_or_literal.source_location,
                )

    def slice_index(
        self,
        begin_index: ExpressionBuilder | Literal | None,
        end_index: ExpressionBuilder | Literal | None,
        stride: ExpressionBuilder | Literal | None,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if stride is not None:
            raise CodeError("Stride is not supported", location=stride.source_location)

        start_expr, start_idx = self._convert_index(begin_index)
        end_expr, end_idx = self._convert_index(end_index)
        slice_types = self.wtype.types[start_idx:end_idx]
        if not slice_types:
            raise CodeError("Empty slices are not supported", location)

        updated_wtype = wtypes.WTuple.from_types(slice_types)
        return var_expression(
            SliceExpression(
                source_location=location,
                base=self.expr,
                begin_index=start_expr,
                end_index=end_expr,
                wtype=updated_wtype,
            )
        )

    def _convert_index(
        self, index: ExpressionBuilder | Literal | None
    ) -> tuple[IntegerConstant | None, int | None]:
        match index:
            case None:
                expr = None
                idx = None
            case Literal(value=int(idx), source_location=start_loc):
                positive_idx = idx if idx >= 0 else len(self.wtype.types) + idx
                positive_idx_clamped = clamp(positive_idx, low=0, high=len(self.wtype.types) - 1)
                expr = UInt64Constant(value=positive_idx_clamped, source_location=start_loc)
            case _:
                raise CodeError(
                    "Tuples can only be indexed with literal values", index.source_location
                )
        return expr, idx

    def iterate(self) -> Iteration:
        return self.rvalue()

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if isinstance(item, Literal):
            raise CodeError(
                "Cannot use in/not in check with a Python literal against a tuple", location
            )
        item_expr = item.rvalue()
        contains_expr = Contains(source_location=location, item=item_expr, sequence=self.expr)
        return var_expression(contains_expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        value = not negate  # if negate is False, return True and vice versa
        logger.warning(f"expression is always {value}", location=location)
        const = BoolConstant(
            location,
            value=value,
        )
        return var_expression(const)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        raise TodoError(location, "TODO: tuple comparison support")
