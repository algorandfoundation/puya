import abc  # TODO: file coverage low
import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ArrayConcat,
    ArrayExtend,
    ArrayLength,
    ArrayPop,
    ConvertArray,
    Copy,
    Expression,
    ExpressionStatement,
    NewArray,
    Statement,
    TupleExpression,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, GenericTypeBuilder
from puyapy.awst_build.eb._utils import (
    dummy_statement,
    dummy_value,
    resolve_array_pop_index,
)
from puyapy.awst_build.eb.arc4._base import arc4_bool_bytes
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.native._base import _ArrayExpressionBuilder
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

__all__ = [
    "ArrayGenericTypeBuilder",
    "ArrayTypeBuilder",
    "ArrayExpressionBuilder",
]

logger = log.get_logger(__name__)


class ArrayGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        if not arg:
            raise CodeError("empty arrays require a type annotation to be instantiated", location)

        arg_item_type = arg.iterable_item_type()
        typ = pytypes.GenericArrayType.parameterise([arg_item_type], location)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)

        if arg.pytype.wtype == wtype:
            new_array: Expression = Copy(value=arg.resolve(), source_location=location)
        elif isinstance(
            arg.pytype.wtype,
            wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray | wtypes.ReferenceArray,
        ):
            new_array = ConvertArray(expr=arg.resolve(), wtype=wtype, source_location=location)
        elif isinstance(arg, StaticSizedCollectionBuilder):
            item_builders = arg.iterate_static()
            items = [ib.resolve() for ib in item_builders]
            new_array = NewArray(values=items, wtype=wtype, source_location=location)
        else:
            logger.error("unsupported collection type", location=arg.source_location)
            new_array = Copy(value=dummy_value(typ, location).resolve(), source_location=location)
        return ArrayExpressionBuilder(new_array, typ)


class ArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericArrayType
        assert typ.size is None
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)

        arg = expect.at_most_one_arg(args, location)
        if not arg:
            new_array: Expression = NewArray(values=[], wtype=wtype, source_location=location)
        else:
            arg_item_type = arg.iterable_item_type()
            if not (typ.items <= arg_item_type):
                logger.error(
                    "iterable element type does not match collection type",
                    location=arg.source_location,
                )
                arg = dummy_value(typ, location)
            if arg.pytype.wtype == wtype:
                new_array = Copy(value=arg.resolve(), source_location=location)
            elif isinstance(
                arg.pytype.wtype,
                wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray | wtypes.ReferenceArray,
            ):
                new_array = ConvertArray(expr=arg.resolve(), wtype=wtype, source_location=location)
            elif isinstance(arg, StaticSizedCollectionBuilder):
                item_builders = arg.iterate_static()
                items = [ib.resolve() for ib in item_builders]
                new_array = NewArray(values=items, wtype=wtype, source_location=location)
            else:
                logger.error("unsupported collection type", location=arg.source_location)
                new_array = Copy(
                    value=dummy_value(typ, location).resolve(), source_location=location
                )

        return ArrayExpressionBuilder(new_array, self._pytype)


class ArrayExpressionBuilder(_ArrayExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        super().__init__(typ, expr)

    @typing.override
    def length(self, location: SourceLocation) -> InstanceBuilder:
        return UInt64ExpressionBuilder(
            ArrayLength(
                array=self.resolve(),
                source_location=location,
            )
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "append":
                return _Append(self.resolve(), self.pytype, location)
            case "extend":
                return _Extend(self.resolve(), self.pytype, location)
            case "pop":
                return _Pop(self.resolve(), self.pytype, location)
            case "freeze":
                return _Freeze(self.resolve(), self.pytype, location)
            case _:
                return super().member_access(name, location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        if op != BuilderBinaryOp.add:
            logger.error(f"unsupported operator for type: {op.value!r}", location=location)
            return dummy_statement(location)
        rhs = _match_array_concat_arg(rhs, self.pytype)
        extend = ArrayExtend(base=self.resolve(), other=rhs.resolve(), source_location=location)
        return ExpressionStatement(expr=extend)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        # only __add__ is implemented, not __radd__
        if op != BuilderBinaryOp.add or reverse:
            return NotImplemented  # type: ignore[no-any-return]

        other = _match_array_concat_arg(other, self.pytype)
        return ArrayExpressionBuilder(
            ArrayConcat(
                left=self.resolve(),
                right=other.resolve(),
                source_location=location,
            ),
            self.pytype,
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        false_builder = ArrayTypeBuilder(self.pytype, location).call([], [], [], location)
        return arc4_bool_bytes(
            self,
            false_builder=false_builder,
            negate=negate,
            location=location,
        )


class _ArrayFunc(FunctionBuilder, abc.ABC):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ


class _Append(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(args, self.typ.items, location)
        args_expr = arg.resolve()
        args_tuple = TupleExpression.from_items([args_expr], arg.source_location)
        return NoneExpressionBuilder(
            ArrayExtend(base=self.expr, other=args_tuple, source_location=location)
        )


class _Pop(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        index = resolve_array_pop_index(self.expr, arg, location)
        result_expr = ArrayPop(base=self.expr, index=index, source_location=location)
        return builder_for_instance(self.typ.items, result_expr)


class _Freeze(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        imm_typ = pytypes.GenericImmutableArrayType.parameterise([self.typ.items], location)
        wtype = imm_typ.checked_wtype(location)
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        result_expr = ConvertArray(expr=self.expr, wtype=wtype, source_location=location)
        return builder_for_instance(imm_typ, result_expr)


class _Extend(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_none)
        if arg is None:
            other = dummy_value(self.typ, location)
        else:
            other = _match_array_concat_arg(arg, self.typ)
        return NoneExpressionBuilder(
            ArrayExtend(base=self.expr, other=other.resolve(), source_location=location)
        )


def _match_array_concat_arg(arg: InstanceBuilder, arr_type: pytypes.ArrayType) -> InstanceBuilder:
    expected_item_type = arr_type.items
    match arg.pytype:
        case pytypes.SequenceType(items=array_items):
            okay = expected_item_type <= array_items
        case pytypes.TupleLikeType(items=tuple_items):
            okay = all(expected_item_type <= ti for ti in tuple_items)
        case _:
            okay = False
    if okay:
        return arg
    logger.error(
        "expected an array or tuple of the same element type", location=arg.source_location
    )
    return dummy_value(arr_type, arg.source_location)
