from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import ArrayAppend, Contains, Expression, Literal, NewArray
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import (
    expect_operand_wtype,
    require_expression_builder,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


class ArrayGenericClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location=location)
        self._storage: wtypes.WType | None = None

    def produces(self) -> wtypes.WType:
        if self._storage is None:
            raise CodeError("A type parameter is required at this location", self.source_location)
        return wtypes.WArray.from_element_type(self._storage)

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if self._storage is not None:
            raise InternalError("Multiple indexing of Array?", location)
        match index:
            case TypeClassExpressionBuilder() as typ_class_eb:
                self.source_location += location
                self._storage = typ_class_eb.produces()
                return self
        raise CodeError(
            "Invalid indexing, only a single type arg is supported",
            location,
        )

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        non_literal_args = [
            require_expression_builder(a, msg="Array arguments must be non literals").rvalue()
            for a in args
        ]
        if self._storage is not None:
            expected_type = self._storage
        elif non_literal_args:
            expected_type = non_literal_args[0].wtype
        else:
            raise CodeError("Empy arrays require a type annotation to be instantiated", location)
        for a in non_literal_args:
            expect_operand_wtype(a, expected_type)
        array_wtype = wtypes.WArray.from_element_type(expected_type)
        array_expr = NewArray(
            source_location=location, elements=tuple(non_literal_args), wtype=array_wtype
        )
        return var_expression(array_expr)


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
        return var_expression(contains_expr)


class ArrayAppenderExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, array: Expression):
        assert isinstance(array.wtype, wtypes.WArray)
        super().__init__(array.source_location)
        self.array = array

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [elem]:
                elem_expr = require_expression_builder(elem).rvalue()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        append_expr = ArrayAppend(
            location,
            array=self.array,
            element=elem_expr,
        )
        return var_expression(append_expr)
