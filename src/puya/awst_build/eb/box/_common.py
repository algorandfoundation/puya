import abc
import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst.nodes import (
    BoxValueExpression,
    BytesRaw,
    StateDelete,
    StateGet,
    StateGetEx,
    Statement,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb._value_proxy import ValueProxyExpressionBuilder
from puya.awst_build.eb.box._util import box_length_checked, index_box_bytes, slice_box_bytes
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import expect_operand_type
from puya.errors import CodeError
from puya.parse import SourceLocation


class _BoxKeyExpressionIntermediateExpressionBuilder(FunctionBuilder, abc.ABC):
    def __init__(self, box: BoxValueExpression, content_type: pytypes.PyType) -> None:
        super().__init__(box.source_location)
        self.box = box
        self.content_type = content_type


class BoxGetExpressionBuilder(_BoxKeyExpressionIntermediateExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if len(args) != 1:
            raise CodeError(f"Expected 1 argument, got {len(args)}", location)
        (default_arg,) = args
        default_expr = expect_operand_type(default_arg, self.content_type).rvalue()
        return builder_for_instance(
            self.content_type,
            StateGet(field=self.box, default=default_expr, source_location=location),
        )


class BoxMaybeExpressionBuilder(_BoxKeyExpressionIntermediateExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if args:
            raise CodeError("Invalid/unexpected args", location)

        return TupleExpressionBuilder(
            StateGetEx(
                field=self.box,
                source_location=location,
            ),
            pytypes.GenericTupleType.parameterise([self.content_type, pytypes.BoolType], location),
        )


class BoxValueExpressionBuilder(ValueProxyExpressionBuilder):
    expr: BoxValueExpression

    def __init__(self, typ: pytypes.PyType, expr: BoxValueExpression):
        super().__init__(typ, expr)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        return StateDelete(field=self.expr, source_location=location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return UInt64ExpressionBuilder(box_length_checked(self.expr, location))
            case "bytes":
                return _ValueBytes(self.expr, location)
            case _:
                return super().member_access(name, location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        if self.pytype != pytypes.BytesType:
            return super().index(index, location)
        return index_box_bytes(self.expr, index, location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        if self.pytype != pytypes.BytesType:
            return super().slice_index(begin_index, end_index, stride, location)

        return slice_box_bytes(self.expr, begin_index, end_index, stride, location)


class _ValueBytes(ValueProxyExpressionBuilder):
    def __init__(self, expr: BoxValueExpression, location: SourceLocation) -> None:
        self._typed = expr
        super().__init__(pytypes.BytesType, BytesRaw(expr=expr, source_location=location))

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return UInt64ExpressionBuilder(box_length_checked(self._typed, location))
            case _:
                return super().member_access(name, location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return index_box_bytes(self._typed, index, location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        return slice_box_bytes(self._typed, begin_index, end_index, stride, location)
