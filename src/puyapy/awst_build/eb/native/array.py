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
    Expression,
    ExpressionStatement,
    Statement,
    TupleExpression,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_statement, dummy_value
from puyapy.awst_build.eb.arc4._base import arc4_bool_bytes
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
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

__all__ = [
    "ArrayGenericTypeBuilder",
    "ArrayTypeBuilder",
    "ArrayExpressionBuilder",
]

logger = log.get_logger(__name__)


class ArrayGenericTypeBuilder(_BaseArrayGenericTypeBuilder):
    def __init__(self, location: SourceLocation) -> None:
        super().__init__(
            generic_typ=pytypes.GenericArrayType,
            eb=ArrayExpressionBuilder,
            expected_wtype_type=wtypes.ARC4DynamicArray,
            location=location,
        )


class ArrayTypeBuilder(_BaseArrayTypeBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        super().__init__(
            typ=typ,
            generic_typ=pytypes.GenericArrayType,
            eb=ArrayExpressionBuilder,
            expected_wtype_type=wtypes.ARC4DynamicArray,
            location=location,
        )


class ArrayExpressionBuilder(_ArrayExpressionBuilder):
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
        expect.no_args(args, location)
        result_expr = ArrayPop(base=self.expr, source_location=location)
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
