import abc
import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ArrayConcat,
    ArrayExtend,
    ArrayPop,
    Expression,
    ExpressionStatement,
    IntrinsicCall,
    NewArray,
    Statement,
    TupleExpression,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder, GenericTypeBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puya.awst_build.eb._utils import (
    dummy_statement,
    dummy_value,
)
from puya.awst_build.eb.arc4._base import _ARC4ArrayExpressionBuilder, arc4_bool_bytes
from puya.awst_build.eb.arc4._utils import no_literal_items
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import BuilderBinaryOp, InstanceBuilder, NodeBuilder
from puya.awst_build.eb.none import NoneExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation

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
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("empty arrays require a type annotation to be instantiated", location)
        element_type = expect.instance_builder(args[0], default=expect.default_raise).pytype
        typ = pytypes.GenericARC4DynamicArrayType.parameterise([element_type], location)
        no_literal_items(typ, location)
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
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        no_literal_items(typ, location)
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
        length = IntrinsicCall(
            op_code="extract_uint16",
            stack_args=[self.resolve(), UInt64Constant(value=0, source_location=location)],
            wtype=wtypes.uint64_wtype,
            source_location=location,
        )
        return UInt64ExpressionBuilder(length)

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
        extend = ArrayExtend(
            base=self.resolve(),
            other=rhs.resolve(),
            wtype=wtypes.void_wtype,
            source_location=location,
        )
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
        if op != BuilderBinaryOp.add:
            return NotImplemented
        if not _check_array_concat_arg(other, self.pytype):
            return NotImplemented

        lhs: InstanceBuilder = self
        rhs = other
        if reverse:
            (lhs, rhs) = (rhs, lhs)
        return DynamicArrayExpressionBuilder(
            ArrayConcat(
                left=lhs.resolve(),
                right=rhs.resolve(),
                wtype=self.pytype.wtype,
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
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(args, self.typ.items, location)
        args_expr = arg.resolve()
        args_tuple = TupleExpression.from_items([args_expr], arg.source_location)
        return NoneExpressionBuilder(
            ArrayExtend(
                base=self.expr, other=args_tuple, wtype=wtypes.void_wtype, source_location=location
            )
        )


class _Pop(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        result_expr = ArrayPop(
            base=self.expr, wtype=self.typ.items.wtype, source_location=location
        )
        return builder_for_instance(self.typ.items, result_expr)


class _Extend(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_none)
        if arg is None:
            other = dummy_value(self.typ, location)
        else:
            other = _match_array_concat_arg(arg, self.typ)
        return NoneExpressionBuilder(
            ArrayExtend(
                base=self.expr,
                other=other.resolve(),
                wtype=wtypes.void_wtype,
                source_location=location,
            )
        )


def _check_array_concat_arg(arg: InstanceBuilder, arr_type: pytypes.ArrayType) -> bool:
    match arg:
        case InstanceBuilder(pytype=pytypes.ArrayType(items=arr_type.items)):
            return True
        case InstanceBuilder(pytype=pytypes.TupleType(items=tup_items)) if all(
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
