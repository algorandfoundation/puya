import typing
from abc import ABC
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
    IndexExpression,
    IntrinsicCall,
    NewArray,
    Statement,
    TupleExpression,
    UInt64Constant,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import FunctionBuilder, GenericTypeBuilder
from puya.awst_build.eb._bytes_backed import (
    BytesBackedInstanceExpressionBuilder,
    BytesBackedTypeBuilder,
)
from puya.awst_build.eb._utils import (
    bool_eval_to_constant,
    compare_bytes,
    expect_exactly_n_args,
    expect_exactly_one_arg,
    expect_no_args,
    resolve_negative_literal_index,
)
from puya.awst_build.eb.arc4.base import CopyBuilder, arc4_bool_bytes
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceBuilder,
    Iteration,
    NodeBuilder,
)
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import require_instance_builder, require_instance_builder_of_type
from puya.errors import CodeError
from puya.parse import SourceLocation

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
        non_literal_args = [require_instance_builder(a) for a in args]
        element_type = non_literal_args[0].pytype

        for a in non_literal_args:
            require_instance_builder_of_type(a, element_type)

        typ = pytypes.GenericARC4DynamicArrayType.parameterise([element_type], location)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        return DynamicArrayExpressionBuilder(
            NewArray(
                values=tuple(a.resolve() for a in non_literal_args),
                wtype=wtype,
                source_location=location,
            ),
            typ,
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
        values = tuple(require_instance_builder_of_type(a, typ.items).resolve() for a in args)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)

        return DynamicArrayExpressionBuilder(
            NewArray(values=values, wtype=wtype, source_location=location), self._pytype
        )


class StaticArrayGenericTypeBuilder(GenericTypeBuilder):
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
        non_literal_args = [require_instance_builder(a) for a in args]
        element_type = non_literal_args[0].pytype
        array_size = len(non_literal_args)
        typ = pytypes.GenericARC4StaticArrayType.parameterise(
            [element_type, pytypes.TypingLiteralType(value=array_size, source_location=None)],
            location,
        )

        for a in non_literal_args:
            require_instance_builder_of_type(a, element_type)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)
        return StaticArrayExpressionBuilder(
            NewArray(
                source_location=location,
                values=tuple(a.resolve() for a in non_literal_args),
                wtype=wtype,
            ),
            typ,
        )


class StaticArrayTypeBuilder(BytesBackedTypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericARC4StaticArrayType
        assert typ.size is not None
        self._size = typ.size
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
        n_args = expect_exactly_n_args(args, location, self._size)
        values = tuple(require_instance_builder_of_type(a, typ.items).resolve() for a in n_args)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)

        return StaticArrayExpressionBuilder(
            NewArray(values=values, wtype=wtype, source_location=location), self.produces()
        )


class _ARC4ArrayExpressionBuilder(BytesBackedInstanceExpressionBuilder[pytypes.ArrayType], ABC):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType):
        super().__init__(typ, expr)

    @typing.override
    def iterate(self) -> Iteration:
        if not self.pytype.items.wtype.immutable:
            logger.error(
                "cannot directly iterate an ARC4 array of mutable objects,"
                " construct a for-loop over the indexes via urange(<array>.length) instead",
                location=self.source_location,
            )
        return self.resolve()

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        array_length = require_instance_builder(
            self.member_access("length", index.source_location)
        )
        index = resolve_negative_literal_index(index, array_length, location)
        result_expr = IndexExpression(
            base=self.resolve(),
            index=index.resolve(),
            wtype=self.pytype.items.wtype,
            source_location=location,
        )
        return builder_for_instance(self.pytype.items, result_expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "copy":
                return CopyBuilder(self.resolve(), location, self.pytype)
            case _:
                return super().member_access(name, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return compare_bytes(lhs=self, op=op, rhs=other, source_location=location)

    @typing.override
    @typing.final
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        raise CodeError("item containment with ARC4 arrays is currently unsupported", location)

    @typing.override
    @typing.final
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing ARC4 arrays is currently unsupported", location)


class DynamicArrayExpressionBuilder(_ARC4ArrayExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        super().__init__(expr, typ)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return UInt64ExpressionBuilder(
                    IntrinsicCall(
                        op_code="extract_uint16",
                        stack_args=[
                            self.resolve(),
                            UInt64Constant(value=0, source_location=location),
                        ],
                        source_location=location,
                        wtype=wtypes.uint64_wtype,
                    )
                )
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
        match op:
            case BuilderBinaryOp.add:
                return ExpressionStatement(
                    expr=ArrayExtend(
                        base=self.resolve(),
                        other=_match_array_concat_arg(
                            rhs, self.pytype, source_location=location
                        ).resolve(),
                        source_location=location,
                        wtype=wtypes.arc4_string_alias,
                    )
                )
            case _:
                return super().augmented_assignment(op, rhs, location)

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
                lhs = self.resolve()
                rhs = _match_array_concat_arg(
                    other, self.pytype, source_location=location
                ).resolve()

                if reverse:
                    (lhs, rhs) = (rhs, lhs)
                return DynamicArrayExpressionBuilder(
                    ArrayConcat(
                        left=lhs,
                        right=rhs,
                        source_location=location,
                        wtype=self.pytype.wtype,
                    ),
                    self.pytype,
                )

            case _:
                return super().binary_op(other, op, location, reverse=reverse)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self,
            false_bytes=b"\x00\x00",
            location=location,
            negate=negate,
        )


class _Append(FunctionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect_exactly_one_arg(args, location)
        args_expr = require_instance_builder_of_type(arg, self.typ.items).resolve()
        args_tuple = TupleExpression.from_items([args_expr], arg.source_location)
        return VoidExpressionBuilder(
            ArrayExtend(
                base=self.expr,
                other=args_tuple,
                source_location=location,
                wtype=wtypes.void_wtype,
            )
        )


class _Pop(FunctionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect_no_args(args, location)
        result_expr = ArrayPop(
            base=self.expr, source_location=location, wtype=self.typ.items.wtype
        )
        return builder_for_instance(self.typ.items, result_expr)


class _Extend(FunctionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect_exactly_one_arg(args, location)
        other = _match_array_concat_arg(arg, self.typ, source_location=location).resolve()
        return VoidExpressionBuilder(
            ArrayExtend(
                base=self.expr,
                other=other,
                source_location=location,
                wtype=wtypes.void_wtype,
            )
        )


def _match_array_concat_arg(
    arg: InstanceBuilder,
    arr_type: pytypes.ArrayType,
    *,
    source_location: SourceLocation,
) -> InstanceBuilder:
    match arg:
        case InstanceBuilder(pytype=pytypes.ArrayType(items=arr_type.items)):
            return arg
        case InstanceBuilder(pytype=pytypes.TupleType(items=tup_items)) if all(
            ti == arr_type.items for ti in tup_items
        ):
            return arg
    raise CodeError("expected an array or tuple of the same element type", source_location)


class StaticArrayExpressionBuilder(_ARC4ArrayExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        size = typ.size
        assert size is not None
        self._size = size
        super().__init__(expr, typ)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return UInt64ExpressionBuilder(
                    UInt64Constant(value=self._size, source_location=location)
                )
            case _:
                return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=self._size > 0, location=location, negate=negate)
