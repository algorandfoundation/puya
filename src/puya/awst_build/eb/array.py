import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import (
    ArrayExtend,
    Contains,
    Expression,
    Literal,
    NewArray,
    TupleExpression,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    FunctionBuilder,
    GenericTypeBuilder,
    InstanceBuilder,
    InstanceExpressionBuilder,
    Iteration,
    NodeBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import expect_operand_type, require_expression_builder
from puya.errors import CodeError
from puya.parse import SourceLocation


class ArrayGenericClassExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("Empy arrays require a type annotation to be instantiated", location)
        non_literal_args = [
            require_expression_builder(a, msg="Array arguments must be non literals") for a in args
        ]
        expected_type = arg_typs[0]
        for a in non_literal_args:
            expect_operand_type(a, expected_type)
        array_type = pytypes.GenericArrayType.parameterise([expected_type], location)
        wtype = array_type.wtype
        assert isinstance(wtype, wtypes.WArray)
        array_expr = NewArray(
            values=tuple(a.rvalue() for a in non_literal_args),
            wtype=wtype,
            source_location=location,
        )
        return ArrayExpressionBuilder(array_expr, array_type)


class ArrayClassExpressionBuilder(TypeBuilder[pytypes.ArrayType]):
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
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        non_literal_args = [
            require_expression_builder(a, msg="Array arguments must be non literals") for a in args
        ]
        array_type = self.produces()
        for a in non_literal_args:
            expect_operand_type(a, array_type.items)
        array_expr = NewArray(
            values=tuple(a.rvalue() for a in non_literal_args),
            wtype=self._wtype,
            source_location=location,
        )
        return ArrayExpressionBuilder(array_expr, array_type)


class ArrayExpressionBuilder(InstanceExpressionBuilder[pytypes.ArrayType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        super().__init__(typ, expr)

    @typing.override
    def iterate(self) -> Iteration:
        return self.rvalue()

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder | Literal:
        match name:
            case "append":
                return _Append(self.expr)
        return super().member_access(name, location)

    @typing.override
    def contains(
        self, item: InstanceBuilder | Literal, location: SourceLocation
    ) -> InstanceBuilder:
        item_expr = expect_operand_type(item, self.pytype.items).rvalue()
        contains_expr = Contains(source_location=location, item=item_expr, sequence=self.expr)
        return BoolExpressionBuilder(contains_expr)

    @typing.override
    def index(self, index: NodeBuilder | Literal, location: SourceLocation) -> NodeBuilder:
        raise NotImplementedError

    @typing.override
    def slice_index(
        self,
        begin_index: NodeBuilder | Literal | None,
        end_index: NodeBuilder | Literal | None,
        stride: NodeBuilder | Literal | None,
        location: SourceLocation,
    ) -> NodeBuilder:
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
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [elem]:
                elem_expr = require_expression_builder(elem).rvalue()

            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        append_expr = ArrayExtend(
            location,
            base=self.array,
            other=TupleExpression.from_items([elem_expr], location),
            wtype=wtypes.void_wtype,
        )
        return VoidExpressionBuilder(append_expr)
