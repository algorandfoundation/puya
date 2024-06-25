import itertools
import typing
from collections.abc import Callable, Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    Contains,
    Expression,
    IntegerConstant,
    IntrinsicCall,
    Lvalue,
    SliceExpression,
    Statement,
    TupleExpression,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import GenericTypeBuilder, InstanceExpressionBuilder
from puya.awst_build.eb._literals import LiteralBuilderImpl
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    Iteration,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
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
        return _init(args, location)


class TupleTypeExpressionBuilder(TypeBuilder[pytypes.TupleType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.TupleType)
        assert typ.generic == pytypes.GenericTupleType
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        result = _init(args, location)
        if result.pytype != self.produces():
            raise CodeError("type mismatch between tuple parameters and argument types", location)
        return result


def _init(args: Sequence[NodeBuilder], location: SourceLocation) -> InstanceBuilder:
    arg = expect.at_most_one_arg(args, location)
    if arg is None:
        return TupleLiteralBuilder(items=[], location=location)

    # TODO: generalise statically-iterable expressions at InstanceBuilder level
    #       e.g. arc4.StaticArray, sequence literals, all should support an "iterate_static"
    #       method that returns a sequence of builders.
    #       This will not just maintain a better cohesion, putting that code closer to the
    #       supporting type, rather than having to update the code here if a new type is added etc.
    #       but will also mean we could use that function in other places, for example we can
    #       easily add support for * unpacking like (*my_static_arr, ...)
    match arg:
        case InstanceBuilder(pytype=pytypes.TupleType(items=t_items)):
            fixed_size = len(t_items)
        case InstanceBuilder(pytype=pytypes.ArrayType(size=int(fixed_size))):
            pass
        case LiteralBuilder(value=bytes(bytes_lit)):
            fixed_size = len(bytes_lit)
        case LiteralBuilder(value=str(str_lit)):
            fixed_size = len(str_lit)
        case _:
            raise CodeError("unhandled argument type", arg.source_location)
    indexer = _make_indexer(arg, location)
    return TupleLiteralBuilder(
        items=[indexer(idx) for idx in range(fixed_size)], location=location
    )


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
    def member_access(
        self, name: str, expr: mypy.nodes.Expression, location: SourceLocation
    ) -> typing.Never:
        if name in dir(tuple()):  # noqa: C408
            raise CodeError("method is not currently supported", location)
        raise CodeError("unrecognised member access", location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        op = BuilderComparisonOp.eq if negate else BuilderComparisonOp.ne
        return _compare(
            self,
            TupleLiteralBuilder([], location),
            op,
            location,
        )

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
    def resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
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

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        return TupleLiteralBuilder(
            items=[item.single_eval() for item in self._items], location=self.source_location
        )


class TupleExpressionBuilder(InstanceExpressionBuilder[pytypes.TupleType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.TupleType)
        super().__init__(typ, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(f"cannot serialize {self.pytype}", location)

    @typing.override
    def member_access(
        self, name: str, expr: mypy.nodes.Expression, location: SourceLocation
    ) -> typing.Never:
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
                        indexer = _make_indexer(self, location)
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
        match index:
            case LiteralBuilder(value=int(index_value)):
                pass
            case _:
                raise CodeError(
                    "tuples can only be indexed by int constants",
                    index.source_location,
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
        op = BuilderComparisonOp.eq if negate else BuilderComparisonOp.ne
        return _compare(
            self,
            TupleLiteralBuilder([], location),
            op,
            location,
        )

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
            chain_op = "&&"
            inverse = BuilderComparisonOp.ne
            result_if_both_empty = True
        case BuilderComparisonOp.ne:
            chain_op = "||"
            inverse = BuilderComparisonOp.eq
            result_if_both_empty = False
        case _:
            raise CodeError(
                f"the {op.value!r} operator is not currently supported with tuples", location
            )
    lhs_indexer = _make_indexer(lhs, location)
    rhs_indexer = _make_indexer(rhs, location)

    lhs_items = [lhs_indexer(idx) for idx, _ in enumerate(lhs.pytype.items)]
    rhs_items = [rhs_indexer(idx) for idx, _ in enumerate(rhs.pytype.items)]

    result_exprs = []
    for idx, (lhs_item, rhs_item) in enumerate(itertools.zip_longest(lhs_items, rhs_items)):
        if lhs_item is None:
            # if lhs is shorter than rhs, use the rhs item to compare against itself,
            # so that rhs is still fully evaluated to maintain semantic compatibility,
            # and we don't create typing errors trying to invent a different eval.
            # make sure it's evaluated once though, because it only appears on one side.
            # also, to make the comparison correct, we need to invert the overall op,
            # if we're doing tup1 == tup2, then things get &&'d together, and we need to use !=
            # if we're doing tup1 != tup2, then things get ||'d together, and we need to use ==
            lhs_item = rhs_item = rhs_item.single_eval()
            op_at = inverse
        elif rhs_item is None:
            rhs_item = lhs_item = lhs_item.single_eval()
            op_at = inverse
        else:
            op_at = op
        cmp_builder = lhs_item.compare(rhs_item, op=op_at, location=location)
        if cmp_builder is NotImplemented:
            cmp_builder = rhs_item.compare(lhs_item, op=op_at.reversed(), location=location)
        if cmp_builder is NotImplemented:
            raise CodeError(
                f"items at index {idx} do not support comparison with operator {op_at.value!r}",
                location,
            )
        result_exprs.append(cmp_builder.resolve())

    if not result_exprs:
        return LiteralBuilderImpl(value=result_if_both_empty, source_location=location)

    result = result_exprs[0]
    for result_expr in result_exprs[1:]:
        result = IntrinsicCall(
            op_code=chain_op,
            stack_args=[result, result_expr],
            wtype=wtypes.bool_wtype,
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

    lhs_indexer = _make_indexer(lhs, location)
    rhs_indexer = _make_indexer(rhs, location)

    items = [
        *(lhs_indexer(idx) for idx in range(len(lhs.pytype.items))),
        *(rhs_indexer(idx) for idx in range(len(rhs.pytype.items))),
    ]
    return TupleLiteralBuilder(items, location)


def _make_indexer(
    builder: InstanceBuilder, location: SourceLocation
) -> Callable[[int], InstanceBuilder]:
    """this function should ONLY be used if ALL elements are going to be visited"""

    if isinstance(builder, TupleLiteralBuilder):
        # this is why this function exists, going through .index() would evaluate to
        # an expression in the general case, but this way we can support comparisons with
        # literal items in tuples naturally
        captured = builder
        return lambda idx: captured.items[idx]

    # in case the tuple expression has side effects
    builder = builder.single_eval()

    def indexer(idx: int) -> InstanceBuilder:
        index_lit = LiteralBuilderImpl(value=idx, source_location=location)
        return builder.index(index_lit, location)

    return indexer
