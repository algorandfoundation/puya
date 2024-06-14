import typing
from collections.abc import Callable, Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BinaryBooleanOperator,
    BooleanBinaryOperation,
    Contains,
    Expression,
    IntegerConstant,
    Lvalue,
    SliceExpression,
    Statement,
    TupleExpression,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import GenericTypeBuilder, InstanceExpressionBuilder, TypeBuilder
from puya.awst_build.eb._literals import LiteralBuilderImpl
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    Iteration,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import clamp, positive_index

logger = log.get_logger(__name__)


class GenericTupleTypeExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("empty tuples are not supported", location)
        if len(args) != 1:
            raise CodeError("tuple constructor takes a single argument")
        inst_args = [require_instance_builder(a) for a in args]
        typ = pytypes.GenericTupleType.parameterise([ia.pytype for ia in inst_args], location)
        tuple_expr = TupleExpression.from_items([ia.resolve() for ia in inst_args], location)
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
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        pytype = self.produces()
        if len(args) != len(pytype.items):
            raise CodeError("")

        tuple_expr = TupleExpression(
            items=[require_instance_builder(a).resolve() for a in args],
            wtype=self._wtype,
            source_location=location,
        )
        return TupleExpressionBuilder(tuple_expr, self.produces())


class TupleLiteralBuilder(InstanceBuilder[pytypes.TupleType]):
    def __init__(self, items: Sequence[InstanceBuilder], location: SourceLocation):
        super().__init__(location)
        self._items = tuple(items)
        self._pytype = pytypes.GenericTupleType.parameterise([i.pytype for i in items], location)

    @typing.override
    @property
    def pytype(self) -> pytypes.TupleType:
        return self._pytype

    @property
    def items(self) -> Sequence[InstanceBuilder]:
        return self._items

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> typing.Never:
        if name in dir(tuple()):  # noqa: C408
            raise CodeError("method is not currently supported", location)
        raise CodeError("unrecognised member access", location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        # TODO: semantic compatibility issue, here and potentially elsewhere: ignores evaluation
        return bool_eval_to_constant(value=bool(self._items), location=location, negate=negate)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(f"cannot serialize {self.pytype}", location)

    @typing.override
    def resolve(self) -> TupleExpression:
        item_exprs = [i.resolve() for i in self.items]
        return TupleExpression.from_items(item_exprs, self.source_location)

    @typing.override
    def resolve_lvalue(self) -> Lvalue:
        return self.resolve()

    @typing.override
    def resolve_literal(self, converter: LiteralConverter) -> InstanceBuilder:
        # even though this may contain literals, it's not homogenous, so we can't really
        # resolve with a single converter currently...?
        return self

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError("cannot delete tuple literal", location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        raise CodeError(f"bad operand type for unary {op.value}: 'tuple'", location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return _compare(self, other, op, location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        match op:
            case BuilderBinaryOp.add:
                return _concat(self, other, location, reverse=reverse)
            case BuilderBinaryOp.mult:
                match other:
                    # can't handle non-simple literals here
                    case LiteralBuilder(value=int(mult_literal)):
                        return TupleLiteralBuilder(self._items * mult_literal, location)
                    case _:
                        raise CodeError("can't multiple sequence by non-int-literal", location)
            case _:
                return NotImplemented

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        raise CodeError("'tuple' is an illegal expression for augmented assignment", location)

    @typing.override
    def iterate(self) -> Iteration:
        return self.resolve()

    def _expr_builder(self) -> InstanceBuilder:
        # used to maintain semantic compatibility, we must resolve this so all elements
        # get evaluated, we can't handle literal indexing or literal containment specially
        return TupleExpressionBuilder(self.resolve(), self.pytype)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._expr_builder().contains(item, location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._expr_builder().index(index, location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        return self._expr_builder().slice_index(begin_index, end_index, stride, location)


class TupleExpressionBuilder(InstanceExpressionBuilder[pytypes.TupleType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.TupleType)
        super().__init__(typ, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(f"cannot serialize {self.pytype}", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> typing.Never:
        if name in dir(tuple()):  # noqa: C408
            raise CodeError("method is not currently supported", location)
        raise CodeError("unrecognised member access", location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        match op:
            case BuilderBinaryOp.add:
                return _concat(self, other, location, reverse=reverse)
            case BuilderBinaryOp.mult:
                match other:
                    # can't handle non-simple literals here
                    case LiteralBuilder(value=int(mult_literal)):
                        indexer = _make_tuple_indexer(self, location)
                        items = [indexer(idx) for idx in range(len(self.pytype.items))]
                        return TupleLiteralBuilder(items * mult_literal, location)
                    case _:
                        raise CodeError("can't multiple sequence by non-int-literal", location)
            case _:
                return NotImplemented

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        # special handling of tuples, they can be indexed by int literal only,
        # mostly because they can be non-homogenous so we need to be able to resolve the
        # result type, but also we can statically validate that value
        index_expr_or_literal = index
        match index_expr_or_literal:
            case LiteralBuilder(value=int(index_value)):
                pass
            case _:
                raise CodeError(
                    "tuples can only be indexed by int constants",
                    index_expr_or_literal.source_location,
                )
        try:
            item_typ = self.pytype.items[index_value]
        except IndexError as ex:
            raise CodeError("tuple index out of range", location) from ex
        item_expr = TupleItemExpression(
            base=self.resolve(),
            index=index_value,
            source_location=location,
        )
        return builder_for_instance(item_typ, item_expr)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        if stride is not None:
            raise CodeError("stride is not supported", location=stride.source_location)

        start_expr, start_idx = self._clamp_slice_index(begin_index)
        end_expr, end_idx = self._clamp_slice_index(end_index)
        slice_types = self.pytype.items[start_idx:end_idx]
        if not slice_types:
            raise CodeError("empty slices are not supported", location)

        updated_type = pytypes.GenericTupleType.parameterise(slice_types, location)
        updated_wtype = updated_type.wtype
        return TupleExpressionBuilder(
            SliceExpression(
                source_location=location,
                base=self.resolve(),
                begin_index=start_expr,
                end_index=end_expr,
                wtype=updated_wtype,
            ),
            updated_type,
        )

    def _clamp_slice_index(
        self, index: NodeBuilder | None
    ) -> tuple[IntegerConstant | None, int | None]:
        match index:
            case None:
                expr = None
                idx = None
            case LiteralBuilder(value=int(idx), source_location=start_loc):
                positive_idx = positive_index(idx, self.pytype.items)
                positive_idx_clamped = clamp(positive_idx, low=0, high=len(self.pytype.items) - 1)
                expr = UInt64Constant(value=positive_idx_clamped, source_location=start_loc)
            case _:
                raise CodeError(
                    "tuples can only be indexed with literal values", index.source_location
                )
        return expr, idx

    @typing.override
    def iterate(self) -> Iteration:
        return self.resolve()

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        contains_expr = Contains(
            sequence=self.resolve(),
            item=item.resolve(),
            source_location=location,
        )
        return BoolExpressionBuilder(contains_expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return _compare(self, other, op, location)


def _compare(
    lhs: InstanceBuilder[pytypes.TupleType],
    rhs: InstanceBuilder,
    op: BuilderComparisonOp,
    location: SourceLocation,
) -> InstanceBuilder:
    if not isinstance(rhs.pytype, pytypes.TupleType):
        return NotImplemented

    match op:
        case BuilderComparisonOp.eq:
            chain_op = BinaryBooleanOperator.and_
            result_if_types_differ = False
        case BuilderComparisonOp.ne:
            chain_op = BinaryBooleanOperator.or_
            result_if_types_differ = True
        case _:
            raise CodeError(
                f"the {op.value!r} operator is not currently supported with tuples", location
            )

    if len(lhs.pytype.items) != len(rhs.pytype.items):
        # TODO: semantic compatibility issue
        return bool_eval_to_constant(value=result_if_types_differ, location=location)

    lhs_indexer = _make_tuple_indexer(lhs, location)
    rhs_indexer = _make_tuple_indexer(rhs, location)

    def compare_at_index(idx: int) -> Expression:
        left = lhs_indexer(idx)
        right = rhs_indexer(idx)
        cmp_builder = left.compare(right, op=op, location=location)
        if cmp_builder is NotImplemented:
            cmp_builder = right.compare(left, op=op.reversed(), location=location)
        if cmp_builder is NotImplemented:
            raise CodeError(
                f"items at index {idx} do not support comparison with operator {op.value!r}",
                location,
            )
        return cmp_builder.resolve()

    result = compare_at_index(0)
    for i in range(1, len(lhs.pytype.items)):
        result = BooleanBinaryOperation(
            left=result,
            right=compare_at_index(i),
            op=chain_op,
            source_location=location,
        )
    return BoolExpressionBuilder(result)


def _concat(
    this: InstanceBuilder[pytypes.TupleType],
    other: InstanceBuilder,
    location: SourceLocation,
    *,
    reverse: bool,
) -> InstanceBuilder:
    if not isinstance(other.pytype, pytypes.TupleType):
        raise CodeError("can only concatenate tuple with other tuples", location)
    other = typing.cast(InstanceBuilder[pytypes.TupleType], other)
    if not reverse:
        lhs, rhs = this, other
    else:
        lhs, rhs = other, this

    lhs_indexer = _make_tuple_indexer(lhs, location)
    rhs_indexer = _make_tuple_indexer(rhs, location)

    items = [
        *(lhs_indexer(idx) for idx in range(len(lhs.pytype.items))),
        *(rhs_indexer(idx) for idx in range(len(rhs.pytype.items))),
    ]
    return TupleLiteralBuilder(items, location)


def _make_tuple_indexer(
    builder: InstanceBuilder, location: SourceLocation
) -> Callable[[int], InstanceBuilder]:
    """this function should ONLY be used if ALL tuple elements are going to be visited"""
    if isinstance(builder, TupleLiteralBuilder):
        # this is why this function exists, going through .index() would evaluate to
        # an expression in the general case, but this way we can support comparisons with
        # literal items in tuples naturally
        captured = builder
        return lambda idx: captured.items[idx]

    def indexer(idx: int) -> InstanceBuilder:
        index_lit = LiteralBuilderImpl(value=idx, source_location=location)
        return builder.index(index_lit, location)

    return indexer
