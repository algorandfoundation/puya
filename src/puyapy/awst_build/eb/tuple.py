import itertools
import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BinaryBooleanOperator,
    BooleanBinaryOperation,
    Expression,
    FieldExpression,
    IntegerConstant,
    IntrinsicCall,
    Lvalue,
    SliceExpression,
    Statement,
    TupleExpression,
    TupleItemExpression,
    UInt64Constant,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import clamp, positive_index
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    InstanceExpressionBuilder,
)
from puyapy.awst_build.eb._literals import LiteralBuilderImpl
from puyapy.awst_build.eb._utils import constant_bool_and_error, dummy_value
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
    TypeBuilder,
)
from puyapy.awst_build.utils import determine_base_type, get_arg_mapping

logger = log.get_logger(__name__)


_TUPLE_MEMBERS: typing.Final = frozenset(("count", "index"))
_NAMED_TUPLE_MEMBERS: typing.Final = frozenset(("_asdict", "_replace"))
_NAMED_TUPLE_CLASS_MEMBERS: typing.Final = frozenset(("_make", "_fields", "_field_defaults"))


class GenericTupleTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _init(args, location)


class TupleTypeBuilder(TypeBuilder[pytypes.TupleType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.TupleType)
        assert typ.generic == pytypes.GenericTupleType
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        result = _init(args, location)
        # equality comparison okay because type constrained to TupleType
        if result.pytype != self.produces():
            raise CodeError("type mismatch between tuple parameters and argument types", location)
        return result


def _init(args: Sequence[NodeBuilder], location: SourceLocation) -> InstanceBuilder:
    arg = expect.at_most_one_arg(args, location)
    if arg is None:
        return TupleLiteralBuilder(items=[], location=location)

    match arg:
        case StaticSizedCollectionBuilder() as static_builder:
            return TupleLiteralBuilder(items=static_builder.iterate_static(), location=location)
        # TODO: maybe LiteralBuilderImpl should be split for str and bytes, so it can
        #       implement StaticSizedCollectionBuilder?
        case LiteralBuilder(value=bytes() | str() as bytes_or_str):
            return TupleLiteralBuilder(
                items=[
                    LiteralBuilderImpl(value=item, source_location=arg.source_location)
                    for item in bytes_or_str
                ],
                location=location,
            )
        case _:
            raise CodeError("unhandled argument type", arg.source_location)


class NamedTupleTypeBuilder(TypeBuilder[pytypes.NamedTupleType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.NamedTupleType)
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        pytype = self.produces()
        field_mapping, any_missing = get_arg_mapping(
            required_positional_names=list(pytype.fields),
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(pytype, location)

        values = [
            expect.argument_of_type_else_dummy(field_mapping[field_name], field_type).resolve()
            for field_name, field_type in pytype.fields.items()
        ]
        expr = TupleExpression(
            items=values,
            wtype=pytype.wtype,
            source_location=location,
        )
        return TupleExpressionBuilder(expr, pytype)

    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name in _NAMED_TUPLE_CLASS_MEMBERS:
            raise CodeError("unsupported member access", location)
        return super().member_access(name, location)


class TupleLiteralBuilder(InstanceBuilder[pytypes.TupleType], StaticSizedCollectionBuilder):
    def __init__(self, items: Sequence[InstanceBuilder], location: SourceLocation):
        super().__init__(location)
        self._items = tuple(items)
        self._pytype = pytypes.GenericTupleType.parameterise([i.pytype for i in items], location)

    @typing.override
    @property
    def pytype(self) -> pytypes.TupleType:
        return self._pytype

    @typing.override
    def iterate_static(self) -> Sequence[InstanceBuilder]:
        return self._items

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> typing.Never:
        if name in _TUPLE_MEMBERS:
            raise CodeError("unsupported member access", location)
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
        item_exprs = [i.resolve() for i in self.iterate_static()]
        return TupleExpression.from_items(item_exprs, self.source_location)

    @typing.override
    def resolve_lvalue(self) -> Lvalue:
        return self.resolve()

    @typing.override
    def resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        return self.try_resolve_literal(converter)

    @typing.override
    def try_resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
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
                        raise CodeError("can't multiply sequence by non-int-literal", location)
            case _:
                return NotImplemented

    @typing.override
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        return super().bool_binary_op(other, op, location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        raise CodeError("'tuple' is an illegal expression for augmented assignment", location)

    @typing.override
    def iterate(self) -> Expression:
        return self.resolve()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return _iterable_item_type(self.pytype, self.source_location)

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


class TupleExpressionBuilder(
    InstanceExpressionBuilder[pytypes.TupleType], StaticSizedCollectionBuilder
):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.TupleType)
        super().__init__(typ, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(f"cannot serialize {self.pytype}", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if isinstance(self.pytype, pytypes.NamedTupleType):
            item_typ = self.pytype.fields.get(name)
            if item_typ is not None:
                item_expr = FieldExpression(
                    base=self.resolve(),
                    name=name,
                    source_location=location,
                )
                return builder_for_instance(item_typ, item_expr)
            elif name == "_replace":
                return _Replace(self, self.pytype, location)
            elif name in _NAMED_TUPLE_MEMBERS:
                raise CodeError("unsupported member access", location)
            elif name in _NAMED_TUPLE_CLASS_MEMBERS:
                type_builder = NamedTupleTypeBuilder(self.pytype, self.source_location)
                return type_builder.member_access(name, location)
        if name in _TUPLE_MEMBERS:
            raise CodeError("unsupported member access", location)
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
                        items = tuple(self.iterate_static())
                        return TupleLiteralBuilder(items * mult_literal, location)
                    case _:
                        raise CodeError("can't multiply sequence by non-int-literal", location)
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
        updated_wtype = updated_type.checked_wtype(location)
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
    def iterate(self) -> Expression:
        return self.resolve()

    @typing.override
    def iterate_static(self) -> Sequence[InstanceBuilder]:
        base = self.single_eval().resolve()
        return [
            builder_for_instance(
                item_type,
                TupleItemExpression(base=base, index=idx, source_location=self.source_location),
            )
            for idx, item_type in enumerate(self.pytype.items)
        ]

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return _iterable_item_type(self.pytype, self.source_location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        contains_expr = None
        if isinstance(item.pytype, pytypes.LiteralOnlyType):
            logger.error(
                "a Python literal is not valid at this location", location=self.source_location
            )
            return dummy_value(pytypes.BoolType, location)
        item = item.single_eval()
        # note: iterate_static single_evals the sequence and is the only usage of self
        for compare_to in self.iterate_static():
            eq_compare = item.compare(compare_to, BuilderComparisonOp.eq, location)
            if eq_compare is NotImplemented:
                eq_compare = compare_to.compare(item, BuilderComparisonOp.eq, location)
            if eq_compare is NotImplemented:
                # if types don't support comparison, then skip
                continue
            if contains_expr is None:
                contains_expr = eq_compare.resolve()
            else:
                contains_expr = BooleanBinaryOperation(
                    left=contains_expr,
                    op=BinaryBooleanOperator.or_,
                    right=eq_compare.resolve(),
                    source_location=location,
                )
        if contains_expr is None:
            return constant_bool_and_error(value=False, location=location)
        else:
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


class _Replace(FunctionBuilder):
    def __init__(
        self,
        instance: TupleExpressionBuilder,
        named_tuple_type: pytypes.NamedTupleType,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.instance = instance
        self.named_tuple_type = named_tuple_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        pytype = self.named_tuple_type
        field_mapping, _ = get_arg_mapping(
            optional_kw_only=list(pytype.fields),
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        base_expr = self.instance.single_eval().resolve()
        items = list[Expression]()
        for idx, (field_name, field_pytype) in enumerate(pytype.fields.items()):
            new_value = field_mapping.get(field_name)
            if new_value is not None:
                item_builder = expect.argument_of_type_else_dummy(new_value, field_pytype)
                item = item_builder.resolve()
            else:
                item = TupleItemExpression(base=base_expr, index=idx, source_location=location)
            items.append(item)
        new_tuple = TupleExpression(items=items, wtype=pytype.wtype, source_location=location)
        return TupleExpressionBuilder(new_tuple, pytype)


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

    assert isinstance(lhs, StaticSizedCollectionBuilder)
    lhs_items = lhs.iterate_static()
    assert isinstance(rhs, StaticSizedCollectionBuilder)
    rhs_items = rhs.iterate_static()

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

    assert isinstance(lhs, StaticSizedCollectionBuilder)
    lhs_items = lhs.iterate_static()
    assert isinstance(rhs, StaticSizedCollectionBuilder)
    rhs_items = rhs.iterate_static()

    items = [*lhs_items, *rhs_items]
    return TupleLiteralBuilder(items, location)


def _iterable_item_type(
    pytype: pytypes.TupleType, source_location: SourceLocation
) -> pytypes.PyType:
    base_type = determine_base_type(*pytype.items, location=source_location)
    if isinstance(base_type, pytypes.UnionType):
        raise CodeError(
            "unable to iterate heterogeneous tuple without common base type", source_location
        )
    return base_type
