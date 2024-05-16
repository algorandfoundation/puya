import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import ArrayExtend, Contains, Expression, Literal, NewArray, TupleExpression
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    IntermediateExpressionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import (
    expect_operand_wtype,
    require_expression_builder,
)
from puya.errors import CodeError
from puya.parse import SourceLocation


class ArrayGenericClassExpressionBuilder(GenericClassExpressionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if not args:
            raise CodeError("Empy arrays require a type annotation to be instantiated", location)
        non_literal_args = [
            require_expression_builder(a, msg="Array arguments must be non literals").rvalue()
            for a in args
        ]
        expected_type = non_literal_args[0].wtype
        for a in non_literal_args:
            expect_operand_wtype(a, expected_type)
        array_wtype = wtypes.WArray(expected_type, location)
        array_expr = NewArray(
            values=tuple(non_literal_args),
            wtype=array_wtype,
            source_location=location,
        )
        return ArrayExpressionBuilder(array_expr)


class ArrayClassExpressionBuilder(TypeClassExpressionBuilder[wtypes.WArray]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericArrayType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WArray)
        super().__init__(wtype, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        non_literal_args = [
            require_expression_builder(a, msg="Array arguments must be non literals").rvalue()
            for a in args
        ]
        array_wtype = self.produces()
        expected_type = array_wtype.element_type
        for a in non_literal_args:
            expect_operand_wtype(a, expected_type)
        array_expr = NewArray(
            values=tuple(non_literal_args),
            wtype=array_wtype,
            source_location=location,
        )
        return ArrayExpressionBuilder(array_expr)


class ArrayExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.WArray)
        self.wtype: wtypes.WArray = expr.wtype
        super().__init__(expr)

    def iterate(self) -> Iteration:
        return self.rvalue()

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "append":
                return ArrayAppenderExpressionBuilder(self.expr)
        return super().member_access(name, location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        item_expr = expect_operand_wtype(item, self.wtype.element_type)
        contains_expr = Contains(source_location=location, item=item_expr, sequence=self.expr)
        return BoolExpressionBuilder(contains_expr)


class ArrayAppenderExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, array: Expression):
        assert isinstance(array.wtype, wtypes.WArray)
        super().__init__(array.source_location)
        self.array = array

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
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
