import structlog

from wyvern.awst import wtypes
from wyvern.awst.nodes import BoolConstant, Contains, Expression, Literal, TupleItemExpression
from wyvern.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    Iteration,
    ValueExpressionBuilder,
)
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.errors import CodeError, TodoError
from wyvern.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


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
        raise TodoError(location, "TODO: slicing tuple")

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
