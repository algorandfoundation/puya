import abc
import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ArrayExtend,
    ArrayLength,
    ArrayPop,
    ConvertArray,
    Expression,
    TupleExpression,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import (
    FunctionBuilder,
)
from puyapy.awst_build.eb._utils import CopyBuilder, dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
)
from puyapy.awst_build.eb.native._base import (
    _ArrayExpressionBuilder,
    _BaseArrayGenericTypeBuilder,
    _BaseArrayTypeBuilder,
)
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

logger = log.get_logger(__name__)


class ReferenceArrayGenericTypeBuilder(_BaseArrayGenericTypeBuilder):
    def __init__(self, location: SourceLocation) -> None:
        super().__init__(
            generic_typ=pytypes.GenericReferenceArrayType,
            eb=ReferenceArrayExpressionBuilder,
            expected_wtype_type=wtypes.ReferenceArray,
            location=location,
        )


class ReferenceArrayTypeBuilder(_BaseArrayTypeBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        super().__init__(
            typ=typ,
            generic_typ=pytypes.GenericReferenceArrayType,
            eb=ReferenceArrayExpressionBuilder,
            expected_wtype_type=wtypes.ReferenceArray,
            location=location,
        )


class ReferenceArrayExpressionBuilder(_ArrayExpressionBuilder):
    @typing.override
    def iterate(self) -> Expression:
        return self.resolve()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self.pytype.items

    @typing.override
    @typing.final
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(
            f"cannot serialize {self.pytype}, try using .freeze() to get an immutable array",
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
        assert isinstance(imm_wtype, wtypes.ARC4DynamicArray)
        converted = ConvertArray(expr=self.expr, wtype=imm_wtype, source_location=location)
        return builder_for_instance(imm_type, converted)


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
