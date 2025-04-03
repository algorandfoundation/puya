import abc
import typing
from collections.abc import Sequence

from puya.awst.nodes import (
    BoxValueExpression,
    ExpressionStatement,
    StateDelete,
    StateGet,
    StateGetEx,
    Statement,
)
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import cast_to_bytes
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.storage._util import box_length_checked, index_box_bytes, slice_box_bytes
from puyapy.awst_build.eb.storage._value_proxy import ValueProxyExpressionBuilder
from puyapy.awst_build.eb.tuple import TupleExpressionBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder


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
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        default_arg_inst = expect.exactly_one_arg_of_type_else_dummy(
            args, self.content_type, location
        )
        default_expr = default_arg_inst.resolve()
        return builder_for_instance(
            self.content_type,
            StateGet(field=self.box, default=default_expr, source_location=location),
        )


class BoxMaybeExpressionBuilder(_BoxKeyExpressionIntermediateExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        result_type = pytypes.GenericTupleType.parameterise(
            [self.content_type, pytypes.BoolType], location
        )
        return TupleExpressionBuilder(
            StateGetEx(field=self.box, source_location=location),
            result_type,
        )


class BoxValueExpressionBuilder(ValueProxyExpressionBuilder[pytypes.PyType, BoxValueExpression]):
    """This is used to intercept operations on Box and BoxMap values to use more efficient
    ops (i.e. box_extract, box_length) where possible and provide support for operations like
    delete"""

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        return ExpressionStatement(
            expr=StateDelete(field=self.resolve(), source_location=location)
        )

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "bytes":
            return _ValueBytes(self.resolve(), location)
        else:
            return super().member_access(name, location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        if pytypes.BytesType <= self.pytype:
            return index_box_bytes(self.resolve(), index, location)
        return super().index(index, location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        if pytypes.BytesType <= self.pytype:
            return slice_box_bytes(self.resolve(), begin_index, end_index, stride, location)
        return super().slice_index(begin_index, end_index, stride, location)


class _ValueBytes(ValueProxyExpressionBuilder):
    def __init__(self, expr: BoxValueExpression, location: SourceLocation) -> None:
        self._typed = expr
        super().__init__(pytypes.BytesType, cast_to_bytes(expr, location))

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
