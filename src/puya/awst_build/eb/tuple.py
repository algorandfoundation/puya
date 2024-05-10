import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BinaryBooleanOperator,
    BoolConstant,
    BooleanBinaryOperation,
    Contains,
    Expression,
    IntegerConstant,
    Literal,
    SliceExpression,
    TupleExpression,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.base import (
    BuilderComparisonOp,
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import require_expression_builder
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import clamp, positive_index

logger = log.get_logger(__name__)


class GenericTupleTypeExpressionBuilder(GenericClassExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        tuple_expr = TupleExpression.from_items(
            [require_expression_builder(a).rvalue() for a in args], location
        )
        return TupleExpressionBuilder(tuple_expr)


class TupleTypeExpressionBuilder(TypeClassExpressionBuilder[wtypes.WTuple]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.TupleType)
        assert typ.generic == pytypes.GenericTupleType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WTuple)
        super().__init__(wtype, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        tuple_expr = TupleExpression(
            items=[require_expression_builder(a).rvalue() for a in args],
            wtype=self.produces(),
            source_location=location,
        )
        return TupleExpressionBuilder(tuple_expr)


class TupleExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType | None = None):  # TODO
        self.pytyp = typ
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
                    base=self.expr,
                    index=index_value,
                    source_location=location,
                )
                return var_expression(item_expr)
            case _:
                raise CodeError(
                    "tuples can only be indexed by int constants",
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

        updated_wtype = wtypes.WTuple(slice_types, location)
        return TupleExpressionBuilder(
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
                positive_idx = positive_index(idx, self.wtype.types)
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
        return BoolExpressionBuilder(contains_expr)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        match op:
            case BuilderComparisonOp.eq:
                chain_op = BinaryBooleanOperator.and_
                result_if_types_differ = False
            case BuilderComparisonOp.ne:
                chain_op = BinaryBooleanOperator.or_
                result_if_types_differ = True
            case _:
                raise CodeError(f"The {op} operator on the tuple type is not supported", location)

        other_expr = require_expression_builder(other).rvalue()
        if self.wtype != other_expr.wtype:
            return BoolExpressionBuilder(
                BoolConstant(value=result_if_types_differ, source_location=location)
            )

        def get_index(expr: Expression, idx: int) -> ExpressionBuilder:
            item = TupleItemExpression(base=expr, index=idx, source_location=location)
            return var_expression(item)

        def compare_at_index(idx: int) -> Expression:
            left = get_index(self.expr, idx)
            right = get_index(other_expr, idx)
            return left.compare(right, op=op, location=location).rvalue()

        result = compare_at_index(0)
        for i in range(1, len(self.wtype.types)):
            result = BooleanBinaryOperation(
                left=result,
                right=compare_at_index(i),
                op=chain_op,
                source_location=location,
            )
        return BoolExpressionBuilder(result)
