import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BinaryBooleanOperator,
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
from puya.awst_build.eb._base import (
    GenericTypeBuilder,
    InstanceExpressionBuilder,
    TypeBuilder,
)
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    Iteration,
    NodeBuilder,
)
from puya.awst_build.utils import require_expression_builder, require_instance_builder
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import clamp, positive_index

logger = log.get_logger(__name__)


class GenericTupleTypeExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = pytypes.GenericTupleType.parameterise(arg_typs, location)
        tuple_expr = TupleExpression.from_items(
            [require_instance_builder(a).rvalue() for a in args], location
        )
        return TupleExpressionBuilder(tuple_expr, typ)


class TupleTypeExpressionBuilder(TypeBuilder[pytypes.TupleType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.TupleType)
        assert typ.generic == pytypes.GenericTupleType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WTuple)
        self._wtype = wtype
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:

        tuple_expr = TupleExpression(
            items=[require_instance_builder(a).rvalue() for a in args],
            wtype=self._wtype,
            source_location=location,
        )
        return TupleExpressionBuilder(tuple_expr, self.produces())


class TupleExpressionBuilder(InstanceExpressionBuilder[pytypes.TupleType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.TupleType)
        super().__init__(typ, expr)

    @typing.override
    def index(self, index: InstanceBuilder | Literal, location: SourceLocation) -> InstanceBuilder:
        # special handling of tuples, they can be indexed by int literal only,
        # mostly because they can be non-homogenous so we need to be able to resolve the
        # result type, but also we can statically validate that value
        index_expr_or_literal = index
        match index_expr_or_literal:
            case Literal(value=int(index_value)):
                return self._index(index_value, location)
            case _:
                raise CodeError(
                    "tuples can only be indexed by int constants",
                    index_expr_or_literal.source_location,
                )

    def _index(self, index_value: int, location: SourceLocation) -> InstanceBuilder:
        try:
            item_typ = self.pytype.items[index_value]
        except IndexError as ex:
            raise CodeError("Tuple index out of bounds", location) from ex
        item_expr = TupleItemExpression(
            base=self.expr,
            index=index_value,
            source_location=location,
        )
        return builder_for_instance(item_typ, item_expr)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | Literal | None,
        end_index: InstanceBuilder | Literal | None,
        stride: InstanceBuilder | Literal | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        if stride is not None:
            raise CodeError("Stride is not supported", location=stride.source_location)

        start_expr, start_idx = self._convert_index(begin_index)
        end_expr, end_idx = self._convert_index(end_index)
        slice_types = self.pytype.items[start_idx:end_idx]
        if not slice_types:
            raise CodeError("Empty slices are not supported", location)

        updated_type = pytypes.GenericTupleType.parameterise(slice_types, location)
        updated_wtype = updated_type.wtype
        return TupleExpressionBuilder(
            SliceExpression(
                source_location=location,
                base=self.expr,
                begin_index=start_expr,
                end_index=end_expr,
                wtype=updated_wtype,
            ),
            updated_type,
        )

    def _convert_index(
        self, index: NodeBuilder | Literal | None
    ) -> tuple[IntegerConstant | None, int | None]:
        match index:
            case None:
                expr = None
                idx = None
            case Literal(value=int(idx), source_location=start_loc):
                positive_idx = positive_index(idx, self.pytype.items)
                positive_idx_clamped = clamp(positive_idx, low=0, high=len(self.pytype.items) - 1)
                expr = UInt64Constant(value=positive_idx_clamped, source_location=start_loc)
            case _:
                raise CodeError(
                    "Tuples can only be indexed with literal values", index.source_location
                )
        return expr, idx

    @typing.override
    def iterate(self) -> Iteration:
        return self.rvalue()

    @typing.override
    def contains(
        self, item: InstanceBuilder | Literal, location: SourceLocation
    ) -> InstanceBuilder:
        if isinstance(item, Literal):
            raise CodeError(
                "Cannot use in/not in check with a Python literal against a tuple", location
            )
        item_expr = item.rvalue()
        contains_expr = Contains(source_location=location, item=item_expr, sequence=self.expr)
        return BoolExpressionBuilder(contains_expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)

    @typing.override
    def compare(
        self, other: InstanceBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        match op:
            case BuilderComparisonOp.eq:
                chain_op = BinaryBooleanOperator.and_
                result_if_types_differ = False
            case BuilderComparisonOp.ne:
                chain_op = BinaryBooleanOperator.or_
                result_if_types_differ = True
            case _:
                raise CodeError(f"The {op} operator on the tuple type is not supported", location)

        other_eb = require_expression_builder(other)
        if not isinstance(other_eb, TupleExpressionBuilder):
            return NotImplemented
        if self.pytype.items != other_eb.pytype.items:
            return bool_eval_to_constant(value=result_if_types_differ, location=location)

        def compare_at_index(idx: int) -> Expression:
            left = self._index(idx, location)
            right = other_eb._index(idx, location)  # noqa: SLF001
            return left.compare(right, op=op, location=location).rvalue()

        result = compare_at_index(0)
        for i in range(1, len(self.pytype.items)):
            result = BooleanBinaryOperation(
                left=result,
                right=compare_at_index(i),
                op=chain_op,
                source_location=location,
            )
        return BoolExpressionBuilder(result)
