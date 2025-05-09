import abc
import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ArrayConcat,
    ArrayExtend,
    ArrayLength,
    ArrayPop,
    Expression,
    IndexExpression,
    NewArray,
    TupleExpression,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    InstanceExpressionBuilder,
)
from puyapy.awst_build.eb._utils import (
    dummy_value,
    resolve_negative_literal_index,
)

# TODO: move these out of ARC-4 ?
from puyapy.awst_build.eb.arc4._base import CopyBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

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
        if not args:
            raise CodeError("empty arrays require a type annotation to be instantiated", location)
        element_type = expect.instance_builder(args[0], default=expect.default_raise).pytype
        typ = pytypes.GenericArrayType.parameterise([element_type], location)
        return ArrayTypeBuilder(typ, self.source_location).call(
            args, arg_kinds, arg_names, location
        )


class ArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericArrayType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ReferenceArray)
        self._wtype = wtype
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
        values = tuple(expect.argument_of_type_else_dummy(a, typ.items).resolve() for a in args)
        return ArrayExpressionBuilder(
            NewArray(values=values, wtype=self._wtype, source_location=location), typ
        )


class ArrayExpressionBuilder(InstanceExpressionBuilder[pytypes.ArrayType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        super().__init__(typ, expr)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        logger.error("item containment with arrays is currently unsupported", location=location)
        return dummy_value(pytypes.BoolType, location)

    @typing.override
    def iterate(self) -> Expression:
        return self.resolve()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self.pytype.items

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        array_length = self.length(index.source_location)
        index = resolve_negative_literal_index(index, array_length, location)
        result_expr = IndexExpression(
            base=self.resolve(),
            index=index.resolve(),
            source_location=location,
        )
        return builder_for_instance(self.pytype.items, result_expr)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing arrays is currently unsupported", location)

    @typing.override
    @typing.final
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(
            f"cannot serialize {self.pytype}," f" try using .freeze() to get an immutable array",
            location,
        )

    def length(self, location: SourceLocation) -> InstanceBuilder:
        return UInt64ExpressionBuilder(ArrayLength(array=self.resolve(), source_location=location))

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return self.length(location)
            case "append":
                return _Append(self.resolve(), self.pytype, location)
            case "extend":
                return _Extend(self.resolve(), self.pytype, location)
            case "pop":
                return _Pop(self.resolve(), self.pytype, location)
            case "freeze":
                return _Freeze(self.resolve(), self.pytype, location)
            case "copy":
                return CopyBuilder(self.resolve(), location, self.pytype)
            case _:
                return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return self.length(location).bool_eval(location, negate=negate)


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
        expect.no_args(args, location)
        result_expr = ArrayPop(base=self.expr, source_location=location)
        return builder_for_instance(self.typ.items, result_expr)


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
        imm_type = pytypes.GenericImmutableArrayType.parameterise([self.typ.items], location)
        imm_wtype = imm_type.wtype
        assert isinstance(imm_wtype, wtypes.StackArray)
        return builder_for_instance(
            imm_type,
            ArrayConcat(
                left=NewArray(wtype=imm_wtype, values=[], source_location=location),
                right=self.expr,
                source_location=location,
            ),
        )


def _check_array_concat_arg(arg: InstanceBuilder, arr_type: pytypes.ArrayType) -> bool:
    match arg:
        case InstanceBuilder(pytype=pytypes.ArrayType(items=arr_type.items)):
            return True
        case InstanceBuilder(pytype=pytypes.TupleLikeType(items=tup_items)) if all(
            ti == arr_type.items for ti in tup_items
        ):
            return True
    return False


def _match_array_concat_arg(arg: InstanceBuilder, arr_type: pytypes.ArrayType) -> InstanceBuilder:
    if _check_array_concat_arg(arg, arr_type):
        return arg
    logger.error(
        "expected an array or tuple of the same element type", location=arg.source_location
    )
    return dummy_value(arr_type, arg.source_location)
