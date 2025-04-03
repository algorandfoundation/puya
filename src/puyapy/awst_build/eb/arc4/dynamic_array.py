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
from puyapy.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puyapy.awst_build.eb._utils import (
    dummy_statement,
    dummy_value,
)
from puyapy.awst_build.eb.arc4._base import _ARC4ArrayExpressionBuilder, arc4_bool_bytes
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import BuilderBinaryOp, InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

__all__ = [
    "DynamicArrayGenericTypeBuilder",
    "DynamicArrayTypeBuilder",
    "DynamicArrayExpressionBuilder",
]

logger = log.get_logger(__name__)


class DynamicArrayGenericTypeBuilder(GenericTypeBuilder):
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
        typ = pytypes.GenericARC4DynamicArrayType.parameterise([element_type], location)
        values = tuple(expect.argument_of_type_else_dummy(a, element_type).resolve() for a in args)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        return DynamicArrayExpressionBuilder(
            NewArray(values=values, wtype=wtype, source_location=location), typ
        )


class DynamicArrayTypeBuilder(BytesBackedTypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericARC4DynamicArrayType
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
        values = tuple(expect.argument_of_type_else_dummy(a, typ.items).resolve() for a in args)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        return DynamicArrayExpressionBuilder(
            NewArray(values=values, wtype=wtype, source_location=location), self._pytype
        )


class DynamicArrayExpressionBuilder(_ARC4ArrayExpressionBuilder):
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
            return NotImplemented

        other = _match_array_concat_arg(other, self.pytype)
        return DynamicArrayExpressionBuilder(
            ArrayConcat(
                left=self.resolve(),
                right=other.resolve(),
                source_location=location,
            ),
            self.pytype,
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self,
            false_bytes=b"\x00\x00",
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
