import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import (
    ArrayExtend,
    Contains,
    Expression,
    NewArray,
    TupleExpression,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    InstanceExpressionBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.interface import InstanceBuilder, Iteration, NodeBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import (
    require_instance_builder,
    require_instance_builder_of_type,
)
from puya.errors import CodeError
from puya.parse import SourceLocation


class ArrayGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("empy arrays require a type annotation to be instantiated", location)
        non_literal_args = [require_instance_builder(a) for a in args]
        expected_type = non_literal_args[0].pytype
        for a in non_literal_args:
            require_instance_builder_of_type(a, expected_type)
        array_type = pytypes.GenericArrayType.parameterise([expected_type], location)
        wtype = array_type.wtype
        assert isinstance(wtype, wtypes.WArray)
        array_expr = NewArray(
            values=tuple(a.resolve() for a in non_literal_args),
            wtype=wtype,
            source_location=location,
        )
        return ArrayExpressionBuilder(array_expr, array_type)


class ArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericArrayType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WArray)
        self._wtype = wtype
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        array_type = self.produces()
        values = tuple(
            require_instance_builder_of_type(a, array_type.items).resolve() for a in args
        )
        array_expr = NewArray(values=values, wtype=self._wtype, source_location=location)
        return ArrayExpressionBuilder(array_expr, array_type)


class ArrayExpressionBuilder(InstanceExpressionBuilder[pytypes.ArrayType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        super().__init__(typ, expr)

    @typing.override
    @typing.final
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError(f"cannot serialize {self.pytype}", location)

    @typing.override
    def iterate(self) -> Iteration:
        return self.resolve()

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "append":
                return _Append(self.resolve())
        return super().member_access(name, location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        item_expr = require_instance_builder_of_type(item, self.pytype.items).resolve()
        contains_expr = Contains(source_location=location, item=item_expr, sequence=self.resolve())
        return BoolExpressionBuilder(contains_expr)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        raise NotImplementedError

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise NotImplementedError

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        raise NotImplementedError


class _Append(FunctionBuilder):
    def __init__(self, array: Expression):
        assert isinstance(array.wtype, wtypes.WArray)
        super().__init__(array.source_location)
        self.array = array

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [elem]:
                elem_expr = require_instance_builder(elem).resolve()

            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        append_expr = ArrayExtend(
            location,
            base=self.array,
            other=TupleExpression.from_items([elem_expr], location),
            wtype=wtypes.void_wtype,
        )
        return VoidExpressionBuilder(append_expr)
